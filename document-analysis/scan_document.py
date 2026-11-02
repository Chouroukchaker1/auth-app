"""Scanner un ou plusieurs formulaires et exporter les données (Excel, PDF, JSON).

100 % local : le modèle Nanonets-OCR2-3B tourne sur votre machine, aucune API.

Exemples :
    python scan_document.py document.png
    python scan_document.py "C:/scans"                 (toutes les images du dossier)
    python scan_document.py document.png --out resultats --debug
"""
import argparse
import sys
from pathlib import Path

from document import load_pages
from export import API_URL, send_json, to_dict, write_excel, write_json, write_pdf
from form_layout import debug_draw, detect_table
from form_reader import merge_pages, read_form
from ocr_engine import LocalOCR

IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}


def collect(inputs):
    images = []
    for item in inputs:
        item = Path(item)
        if item.is_dir():
            images += sorted(p for p in item.iterdir() if p.suffix.lower() in IMAGE_TYPES)
        elif item.is_file():
            images.append(item)
        else:
            print(f"Introuvable : {item}")
    return images


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description="Extraire les données d'un formulaire scanné (modèle local)")
    parser.add_argument("images", nargs="*", default=[str(Path(__file__).parent / "exemples" / "document.png")],
                        help="Images ou dossiers à scanner (défaut : exemples/document.png)")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("resultats"),
                        help="Dossier de sortie (défaut : resultats/)")
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None, help="Forcer CPU ou GPU")
    parser.add_argument("--debug", action="store_true", help="Enregistre l'image redressée avec la grille détectée")
    parser.add_argument("--api", default=API_URL or None,
                        help="Adresse de l'API qui reçoit le résultat JSON (défaut : variable OCR_API_URL)")
    args = parser.parse_args()

    images = collect(args.images)
    if not images:
        parser.error("aucune image à scanner")
    args.out.mkdir(parents=True, exist_ok=True)

    print("Chargement du modèle local...")
    ocr = LocalOCR(device=args.device)
    print(f"Modèle prêt sur {ocr.device}.")

    for image_path in images:
        print(f"\n=== {image_path.name} ===")
        result = merge_pages([read_form(ocr, page, source=str(image_path)) for page in load_pages(image_path)])
        stem = args.out / image_path.stem
        write_excel(result, stem.with_suffix(".xlsx"))
        write_pdf(result, stem.with_suffix(".pdf"))
        write_json(result, stem.with_suffix(".json"))
        if args.api:
            try:
                status, answer = send_json(to_dict(result), args.api)
                print(f"Résultat envoyé à l'API (code {status}). Réponse : {answer}")
            except Exception as error:  # l'analyse est gardée sur le disque même si l'envoi échoue
                print(f"Envoi à l'API impossible ({error}) : le JSON reste dans {stem}.json")
        if args.debug:
            table = detect_table(result.page)
            debug_draw(result.page, table, [(b[1], b[3]) for b, _ in result.strips],
                       f"{stem}_grille.png")

        print("\nChamps :")
        for f in result.fields:
            flag = "  <- à vérifier" if f["conf"] < 0.55 else ""
            print(f"  {f['label']} : {f['value']}{flag}")
        if result.rows:
            print("Tableau :")
            print("  " + " | ".join(result.headers))
            for cells in result.rows:
                print("  " + " | ".join(c.text for c in cells))
        print(f"\nTerminé en {result.seconds:.0f} s. Fichiers : {stem}.xlsx / .pdf / .json")


if __name__ == "__main__":
    main()
