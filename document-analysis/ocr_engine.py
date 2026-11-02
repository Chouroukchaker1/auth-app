"""Moteur OCR 100 % local (aucune API) basé sur Nanonets-OCR2-3B.

- float32 sur CPU (3x plus rapide que bfloat16 sur les processeurs sans AMX)
- float16/bfloat16 sur GPU NVIDIA si une version CUDA de torch est installée
- renvoie un score de confiance (probabilité moyenne et minimale des tokens)
- peut comparer des réponses candidates (vocabulaire fermé) avec le modèle lui-même
"""
import copy
import logging
import os
import warnings

import torch
from PIL import Image, ImageOps

warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("bitsandbytes").setLevel(logging.ERROR)  # « MatMul8bitLt: inputs will be cast… » à chaque appel
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from transformers import AutoModelForImageTextToText, AutoProcessor  # noqa: E402

MODEL_PATH = "nanonets/Nanonets-OCR2-3B"
SCORE_BATCH = 16  # candidats notés ensemble par score_candidates (mémoire graphique : ~30 Mo par candidat)


class OCRResult(tuple):
    """(text, conf, min_conf, lines) où lines = [(ligne, confiance)]."""

    def __new__(cls, text, conf, min_conf, lines):
        return super().__new__(cls, (text, conf, min_conf, lines))

    text = property(lambda self: self[0])
    conf = property(lambda self: self[1])
    min_conf = property(lambda self: self[2])
    lines = property(lambda self: self[3])


def load_model(model_path=MODEL_PATH, device="cpu", threads=None, quantize=None):
    """Charge le modèle : float32 sur CPU ; sur GPU bf16/fp16, ou compressé (quantize = "4bit"
    ou "8bit") si la carte a moins de 10 Go (le modèle 3B en bf16 occupe 7,5 Go, trop pour
    une RTX 3050 6 Go). Variable d'environnement OCR_QUANTIZE pour forcer le choix."""
    if device == "cuda":
        dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        kwargs = {"dtype": dtype, "device_map": {"": 0}}
        quantize = quantize or os.environ.get("OCR_QUANTIZE")
        if quantize is None and torch.cuda.get_device_properties(0).total_memory / 2**30 < 10:
            quantize = "8bit"
        if quantize in ("4bit", "8bit"):
            from transformers import BitsAndBytesConfig

            if quantize == "4bit":
                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype,
                    bnb_4bit_use_double_quant=True)
            else:
                kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        return AutoModelForImageTextToText.from_pretrained(model_path, **kwargs)
    torch.set_num_threads(threads or max(1, (os.cpu_count() or 2) // 2))
    return AutoModelForImageTextToText.from_pretrained(model_path, dtype=torch.float32).to(device)


class LocalOCR:
    def __init__(self, model_path=MODEL_PATH, device=None, threads=None, adapter=None):
        """adapter : dossier d'un complément LoRA appris (ex. adapters/khatt), ou variable
        d'environnement OCR_ADAPTER. Sans adapter, le modèle d'origine est utilisé."""
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.model = load_model(model_path, device, threads)
        adapter = adapter or os.environ.get("OCR_ADAPTER")
        if adapter:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, adapter)
        self.adapter = adapter
        self.model.eval()

    @staticmethod
    def prepare(image, min_height=96, max_side=1800, border=16):
        """Agrandit les petits crops et ajoute une marge blanche (meilleure lecture)."""
        image = image.convert("RGB")
        if image.height < min_height:
            factor = min_height / image.height
            image = image.resize((int(image.width * factor), min_height), Image.LANCZOS)
        if max(image.size) > max_side:
            factor = max_side / max(image.size)
            image = image.resize((int(image.width * factor), int(image.height * factor)), Image.LANCZOS)
        return ImageOps.expand(image, border=border, fill=(255, 255, 255))

    def _inputs(self, image, prompt, answer=None):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]},
        ]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        if answer is not None:
            text += answer
        return self.processor(text=[text], images=[image], return_tensors="pt").to(self.model.device)

    @torch.inference_mode()
    def read(self, image, prompt, max_new_tokens=128):
        """Retourne OCRResult(texte, confiance_moyenne, confiance_min, confiance_par_ligne)."""
        image = self.prepare(image)
        inputs = self._inputs(image, prompt)
        out = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            repetition_penalty=1.05,
            output_scores=True,
            return_dict_in_generate=True,
        )
        generated = out.sequences[:, inputs.input_ids.shape[1]:]
        text = self.processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
        scores = self.model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)[0]
        probs = scores.float().exp()
        special = set(self.processor.tokenizer.all_special_ids)
        tokens = [(tok, p) for tok, p in zip(generated[0].tolist(), probs.tolist()) if tok not in special]
        if not tokens:
            return OCRResult(text, 0.0, 0.0, [])
        keep = [p for _, p in tokens]
        # Confiance par ligne : on regroupe les tokens entre deux retours à la ligne
        groups, current = [], []
        for tok, p in tokens:
            current.append((tok, p))
            if "\n" in self.processor.tokenizer.decode([tok]):
                groups.append(current)
                current = []
        groups.append(current)
        per_line = []
        for group in groups:
            for line in self.processor.tokenizer.decode([t for t, _ in group]).split("\n"):
                if line.strip():
                    per_line.append((line.strip(), sum(p for _, p in group) / len(group)))
        return OCRResult(text, sum(keep) / len(keep), min(keep), per_line)

    @torch.inference_mode()
    def read_hypotheses(self, image, prompt, n=4, max_new_tokens=40):
        """Recherche en faisceau : renvoie les n meilleures lectures [(texte, score)]."""
        image = self.prepare(image)
        inputs = self._inputs(image, prompt)
        out = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            num_beams=n,
            num_return_sequences=n,
            output_scores=True,
            return_dict_in_generate=True,
        )
        texts = self.processor.batch_decode(out.sequences[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        scores = out.sequences_scores.float().tolist()
        seen, result = set(), []
        for text, score in zip(texts, scores):
            text = text.strip()
            if text and text not in seen:
                seen.add(text)
                result.append((text, score))
        return result

    @torch.inference_mode()
    def score_candidates(self, image, prompt, candidates, prefix="", complete=None):
        """Log-probabilité moyenne par token de chaque candidat, sachant l'image
        (et un début de réponse imposé `prefix`, ex. « …الرتبة: »).
        Sert à choisir une valeur dans une liste fermée (ex. lien de parenté, grade).
        L'image et le début ne sont calculés qu'une fois (cache) ; les candidats sont ensuite
        notés ensemble, par lots, en un seul passage du modèle par lot.

        complete : texte qui suit obligatoirement une réponse finie (« <|im_end|> », « \\n »).
        On renvoie alors la log-probabilité totale du candidat suivi de ce texte : la vraie
        probabilité de la réponse entière, à utiliser pour la confiance (la moyenne par token
        ne pénalise pas un mot coupé, « المنخرط » / « المنخرطة » se partagent alors la même lecture)."""
        image = self.prepare(image)
        base = self._inputs(image, prompt, answer=prefix or None)
        length = base.input_ids.shape[1]
        out = self.model(**base, use_cache=True)
        first = torch.log_softmax(out.logits[0, -1].float(), -1)
        tokenizer = self.processor.tokenizer
        encoded = [(cand, tokenizer(cand + (complete or ""), add_special_tokens=False).input_ids)
                   for cand in dict.fromkeys(candidates)]
        encoded = [(cand, ids) for cand, ids in encoded if ids]
        pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
        results = {}
        for start in range(0, len(encoded), SCORE_BATCH):
            batch = encoded[start:start + SCORE_BATCH]
            width = max(len(ids) for _, ids in batch)
            # Complétés à droite : un token ne voit que ceux d'avant, le remplissage n'influe pas
            ids = torch.tensor([ids + [pad] * (width - len(ids)) for _, ids in batch], device=self.model.device)
            cache = copy.deepcopy(out.past_key_values)
            cache.batch_repeat_interleave(len(batch))
            step = self.model(input_ids=ids, past_key_values=cache,
                              cache_position=torch.arange(length, length + width, device=ids.device), use_cache=True)
            logp = torch.log_softmax(step.logits[:, :-1].float(), -1)
            for row, (cand, cand_ids) in enumerate(batch):
                token_logp = torch.stack([first[cand_ids[0]]] + [logp[row, j - 1, tok]
                                                                for j, tok in enumerate(cand_ids) if j])
                results[cand] = float(token_logp.sum() if complete else token_logp.mean())
        return results
