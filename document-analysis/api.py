"""Service d'analyse de document appelé par le backend Spring Boot (/api/analyses).

100 % local (modèle Nanonets-OCR2-3B sur cette machine). Lancer avec :
    python api.py                    (http://localhost:8501)

Une analyse prend plusieurs minutes : POST /analyses la met en file et répond tout de suite
avec un identifiant ; GET /analyses/{id} donne l'avancement puis le résultat.
Les analyses passent une par une (le modèle occupe toute la carte graphique).
"""
import contextlib
import io
import os
import queue
import re
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from document import load_pages
from export import to_dict
from form_link import to_member_form
from form_reader import merge_pages, read_form

ROOT = Path(__file__).parent
UPLOADS = ROOT / "resultats" / "documents"
MAX_BYTES = 20 * 1024 * 1024
KEEP_JOBS = 30
MODEL_RAM_GB = 13  # le modèle en float32 sur CPU occupe environ 12-15 Go
MODEL_VRAM_GB = 4.5  # en 8 bits sur la carte graphique

jobs = {}
waiting = queue.Queue()
model = {"ocr": None, "state": "loading", "error": None}


# ---------------------------------------------------------------- modèle
def missing_memory_gb():
    """Go manquants pour charger le modèle (0 si la mémoire suffit)."""
    import psutil
    import torch

    if torch.cuda.is_available():
        return max(0.0, MODEL_VRAM_GB - torch.cuda.mem_get_info()[0] / 2**30)
    return max(0.0, MODEL_RAM_GB - psutil.virtual_memory().available / 2**30)


def load_model():
    """Chargé une fois au démarrage : la première analyse n'attend pas le modèle."""
    try:
        missing = missing_memory_gb()
        if missing:
            raise MemoryError(f"mémoire insuffisante pour charger le modèle (il manque environ {missing:.1f} Go)")
        from ocr_engine import LocalOCR  # import lourd (torch, transformers)

        model["ocr"] = LocalOCR()
        model["state"] = "ready"
        print(f"Modèle prêt sur {model['ocr'].device}.", flush=True)
    except Exception as error:  # le service reste joignable et explique le problème
        model["state"], model["error"] = "error", str(error)
        print(f"Chargement du modèle impossible : {error}", flush=True)


# ---------------------------------------------------------------- analyses
def progress_of(job, message):
    """Avancement approximatif d'après le journal de read_form (0-100)."""
    page = job["page_index"] / job["pages"]
    share = 1 / job["pages"]
    table = re.search(r"trouvé, (\d+) lignes", message)
    if table:
        job["rows"] = int(table.group(1))
    if message.startswith("Lecture de la partie haute"):
        step = 0.08
    elif message.startswith("  bande"):
        step = min(0.35, job["step"] + 0.06)
    elif message.startswith("Lecture du tableau"):
        step = 0.4
    else:
        row = re.match(r"  ligne (\d+) :", message)
        step = 0.4 + 0.55 * int(row.group(1)) / job["rows"] if row and job.get("rows") else job["step"]
    job["step"] = max(job["step"], step)
    return min(99, int(100 * (page + share * job["step"])))


def run(job):
    job.update(status="running", started=time.time())
    try:
        while model["state"] == "loading":
            job["message"] = "Chargement du modèle..."
            time.sleep(1)
        if model["state"] == "error":
            raise RuntimeError(model["error"])
        pages = load_pages(job["path"])
        job["pages"] = len(pages)
        results = []
        for index, page in enumerate(pages):
            job.update(page_index=index, step=0.0, rows=None)

            def log(message, job=job, index=index):
                text = str(message)
                job["progress"] = progress_of(job, text)
                job["message"] = (f"Page {index + 1}/{len(pages)} · " if len(pages) > 1 else "") + text.strip()

            results.append(read_form(model["ocr"], page, log=log, source=job["filename"]))
        result = merge_pages(results)
        job["page"] = result.page
        data = to_dict(result)
        job.update(status="done", progress=100, message="Analyse terminée", data=data,
                   memberForm=to_member_form(data), seconds=round(time.time() - job["started"]))
    except Exception as error:
        job.update(status="error", error=str(error))
        print(f"Analyse {job['id']} impossible : {error}", flush=True)


def worker():
    load_model()
    while True:
        run(waiting.get())


def public(job):
    position = sum(1 for other in jobs.values() if other["status"] == "queued" and other["created"] < job["created"])
    fields = ("id", "status", "progress", "message", "error", "data", "memberForm", "seconds", "pages")
    return {**{key: job.get(key) for key in fields}, "position": position}


# ---------------------------------------------------------------- routes HTTP
async def health(_):
    ocr = model["ocr"]
    return JSONResponse({"model": model["state"], "device": ocr.device if ocr else None, "error": model["error"]})


async def create_analysis(request):
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return JSONResponse({"message": "Aucun fichier reçu (champ « file »)"}, status_code=400)
    content = await upload.read()
    if not content:
        return JSONResponse({"message": "Fichier vide"}, status_code=400)
    if len(content) > MAX_BYTES:
        return JSONResponse({"message": "Fichier trop volumineux (20 Mo maximum)"}, status_code=413)
    try:
        load_pages(io.BytesIO(content), check_only=True)
    except ValueError as error:
        return JSONResponse({"message": str(error)}, status_code=400)
    job_id = uuid.uuid4().hex
    UPLOADS.mkdir(parents=True, exist_ok=True)
    path = UPLOADS / f"{job_id}{Path(upload.filename or '').suffix.lower()[:6]}"
    path.write_bytes(content)
    job = {"id": job_id, "status": "queued", "progress": 0, "message": "En attente", "created": time.time(),
           "path": path, "filename": upload.filename or path.name, "pages": 1, "page_index": 0, "step": 0.0}
    for old in sorted(jobs.values(), key=lambda j: j["created"])[:max(0, len(jobs) - KEEP_JOBS + 1)]:
        if old["status"] in ("done", "error"):
            jobs.pop(old["id"], None)
            Path(old["path"]).unlink(missing_ok=True)
    jobs[job_id] = job
    waiting.put(job)
    return JSONResponse(public(job), status_code=202)


async def get_analysis(request):
    job = jobs.get(request.path_params["job_id"])
    if job is None:
        return JSONResponse({"message": "Analyse introuvable"}, status_code=404)
    return JSONResponse(public(job))


async def get_page(request):
    """Page redressée (celle que le modèle a lue), affichée à côté des résultats."""
    job = jobs.get(request.path_params["job_id"])
    if job is None or job.get("page") is None:
        return JSONResponse({"message": "Image non disponible"}, status_code=404)
    buffer = io.BytesIO()
    job["page"].save(buffer, format="JPEG", quality=85)
    return Response(buffer.getvalue(), media_type="image/jpeg")


async def member_form(request):
    """Valeurs du formulaire adhérent recalculées après les corrections faites à la main."""
    data = await request.json()
    if not isinstance(data, dict) or "fields" not in data or "table" not in data:
        return JSONResponse({"message": "Résultat d'analyse attendu (fields, table)"}, status_code=400)
    return JSONResponse(to_member_form(data))


@contextlib.asynccontextmanager
async def lifespan(_):
    threading.Thread(target=worker, daemon=True).start()
    yield


app = Starlette(routes=[
    Route("/health", health),
    Route("/analyses", create_analysis, methods=["POST"]),
    Route("/analyses/{job_id}", get_analysis),
    Route("/analyses/{job_id}/page", get_page),
    Route("/member-form", member_form, methods=["POST"]),
], lifespan=lifespan)


if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("OCR_HOST", "127.0.0.1"), port=int(os.environ.get("OCR_PORT", "8501")),
                log_level="warning")
