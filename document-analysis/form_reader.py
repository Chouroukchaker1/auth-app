"""Lecture structurée d'un formulaire (champs du haut + tableau) avec le modèle local.

Étapes :
 1. redressement de la photo (perspective + inclinaison) ;
 2. détection du quadrillage du tableau, cellule par cellule ;
 3. partie haute lue en bandes qui se chevauchent, puis fusion des lignes ;
 4. tableau lu cellule par cellule (cellules vides ignorées grâce à la mesure d'encre) ;
 5. post-traitement : guillemets de répétition, flèches, dates, nom de famille commun,
    vocabulaire des liens de parenté, score de confiance pour chaque valeur.
"""
import math
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import cv2
import numpy as np
from PIL import Image

from form_layout import (binarize, crossed_out, deskew, detect_table, find_boxes, ink_ratio, load_image,
                         middle_gap, straighten_page)

PROMPT_LINES = (
    "Transcribe all text in this image line by line, exactly as written: printed labels and handwritten "
    "values, in Arabic and French. Keep the colon between a label and its value. "
    "Do not translate, correct or add anything."
)
PROMPT_HEADER = "Transcribe exactly the printed or handwritten text in this table header cell. Output only the text."
PROMPT_CELL = (
    "Transcribe exactly the handwritten text in this table cell. It may be Arabic or French. "
    "Output only the text, nothing else."
)
PROMPT_NAME = (
    "This table cell contains a handwritten Arabic person name (first name followed by family name). "
    "Transcribe it letter by letter in Arabic script. Output only the name."
)
PROMPT_DATE = (
    "This table cell contains a handwritten date, or a ditto mark meaning 'same as above'. "
    "Output only what is written."
)

PROMPT_NUMBER = (
    "This box contains a handwritten number written digit by digit. "
    "Output only the digits, without spaces, nothing else."
)

PROMPT_FAMILY = (
    "This table cell contains a handwritten Arabic person name: a first name followed by a family name. "
    "Output only the family name."
)

INK_THRESHOLD = 0.012
FAMILY_MARGIN = 1.5  # écart de log-probabilité toléré pour aligner le nom de famille d'une ligne
NAME_RIVAL = 0.5  # ressemblance minimale d'un prénom connu pour concurrencer le prénom lu
GRADE_MARGIN = 2.0  # idem pour remplacer la lecture du grade par un grade connu
NUMBER_SURE_CONF = 0.8  # en dessous, un numéro lu dans une case encadrée est signalé « à vérifier »
RELATION_MAX_CONF = 0.6  # en dessous, la lecture libre du lien de parenté est vérifiée avec le vocabulaire
RELATION_MARGIN = 2.0  # écart de log-probabilité moyenne toléré (mesuré sur document.png)
UNKNOWN_RELATION_CONF = 0.6  # plafond de confiance d'un mot inconnu dans la colonne « lien de parenté »
FOREIGN_SCRIPT_CONF = 0.5  # plafond si la lecture contient du grec / cyrillique (« 1μs » pour « 1ميا »)
DITTO = "〃"
ARROW = "↓"
END = "<|im_end|>"  # fin de réponse du modèle : note la réponse entière pour la confiance

# Mots connus dans la colonne « lien de parenté »
RELATION_WORDS = ["المنخرط", "المنخرطة", "الزوجة", "الزوج", "الابن", "الابنة", "البنت", "الأب", "الأم"]

# Prénoms courants par genre : accorde le lien de parenté peu sûr avec le prénom
# (« مريم » -> الزوجة et non الزوج, « سليم » -> الابن et non البنت)
FEMALE_NAMES = set(
    "مريم فاطمة عائشة خديجة زينب سارة سلمى سلوى سميرة سعاد سهام سناء سنية ليلى لمياء منى منية نادية نجاة "
    "نجلاء نورة نور هدى هند هالة وفاء ياسمين يسرى آمال أمال أحلام أسماء إيمان ألفة أميرة بثينة بسمة جميلة "
    "حنان حياة خولة دنيا رانية رحمة رجاء ريم زهرة شيماء صفاء عبير عفاف فريدة كوثر لطيفة نسرين هاجر وداد".split())
MALE_NAMES = set(
    "محمد أحمد محمود علي حسن حسين أحسن عمر عثمان يوسف إبراهيم إسماعيل خالد سليم سالم سلام سامي سمير كريم كمال "
    "جمال نبيل نافع ناجع ناجح نجيب رضا رياض فتحي فيصل فاروق فوزي منير مراد مصطفى مهدي منصف لطفي الهادي "
    "الطاهر الحبيب بشير توفيق حمزة حمادي حاتم حافظ حكيم رشيد زياد زهير صالح صلاح صابر طارق عادل عماد عزيز "
    "عصام غسان قيس لسعد مالك مجدي محسن معز مكرم ناصر نزار هشام وليد ياسين يحيى أسامة أنيس أيمن أمين إلياس "
    "بلال شكري شاكر منذر ماهر مختار رؤوف سفيان أشرف أكرم بسام جلال حسام رامي فراس مازن نضال".split())
GENDER_PAIRS = {"الزوج": "الزوجة", "الابن": "البنت", "الأب": "الأم", "المنخرط": "المنخرطة"}

# Grades (sécurité / police / garde) pour le champ « الرتبة »
GRADES = [
    "عون أمن", "حافظ أمن", "حافظ شرطة", "عريف", "عريف أول", "رقيب", "رقيب أول", "وكيل", "وكيل أول",
    "مفتش شرطة", "مفتش شرطة أول", "ضابط شرطة", "ضابط شرطة أول", "محافظ شرطة", "محافظ شرطة أول",
    "محافظ شرطة عام", "ملازم", "ملازم أول", "نقيب", "رائد", "مقدم", "عقيد", "عميد", "متفقد شرطة",
]

# Libellés connus du formulaire (pour normaliser ce que lit le modèle)
KNOWN_LABELS = [
    "الاسم الإداري الكامل", "تاريخ ومكان الولادة", "الرتبة", "تاريخ مباشرة العمل", "الرقم القياسي",
    "تاريخ عقد الزواج", "رقم الانخراط", "الرقم الموحد", "رقم البطاقة", "رقم الجراية", "رقم الاشتراك",
    "الرقم المعتمد", "ملاحظات", "N° F", "Carte de Soin", "Centre de Soin", "Carte Militaire",
]


@dataclass
class Cell:
    row: int
    col: int
    box: tuple
    text: str = ""
    conf: float = 1.0
    raw: str = ""
    note: str = ""
    image: object = None
    scores: dict = None  # notes du modèle pour chaque mot connu (lien de parenté choisi dans la liste)


@dataclass
class FormResult:
    source: str
    page: object = None
    fields: list = field(default_factory=list)  # dicts: label, value, conf, note, raw
    headers: list = field(default_factory=list)
    rows: list = field(default_factory=list)  # list[list[Cell]]
    raw_lines: list = field(default_factory=list)
    strips: list = field(default_factory=list)  # (box, image)
    seconds: float = 0.0


# ---------------------------------------------------------------- utilitaires texte
def norm(text):
    text = re.sub(r"[ً-ْـ]", "", text)  # harakat + tatweel
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"[\s\.\-_:…]+", "", text).lower()


def similar(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def clean_value(value):
    value = re.sub(r"[\.…_]{3,}", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" :-–|")
    if not re.search(r"[\w؀-ۿ]", value):
        return ""
    return value


def normalize_date(value):
    """10 - 10 - 1980 / 10/10/1980 -> 1980-10-10 (si la date est complète et valide)."""
    digits = re.findall(r"\d+", value)
    if len(digits) == 3:
        if len(digits[0]) == 4:
            y, m, d = digits
        elif len(digits[2]) == 4:
            d, m, y = digits
        else:
            return None
        if y == "0000" or d.strip("0") == "" or m.strip("0") == "":
            return f"{y}/{m.zfill(2)}/{d.zfill(2)}" if y == "0000" else None
        if 1 <= int(m) <= 12 and 1 <= int(d) <= 31 and 1900 <= int(y) <= 2100:
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return None


def impossible_date(value):
    """Mois > 12 ou jour > 31 (ex. « 0000/20/00 ») : un chiffre est forcément mal lu."""
    digits = re.findall(r"\d+", value)
    if len(digits) != 3:
        return False
    d, m = (digits[2], digits[1]) if len(digits[0]) == 4 else (digits[0], digits[1])
    return int(m) > 12 or int(d) > 31


def sanitize(text):
    """Supprime les sorties parasites du modèle sur les zones raturées ou vides.
    Retourne (texte, remarque) ; texte vide si la sortie est inexploitable."""
    raw = text
    # Une signature n'est pas du texte : le modèle y « lit » un nom inventé (« Carole Ch »)
    text = re.sub(r"<signature>.*?</signature>", "", text, flags=re.S)
    text = re.sub(r"</?(signature|watermark|page_number|img)[^>]*>", "", text).strip()
    if "\\frac" in text or text.count("$") >= 2 or "\\" in text:
        return "", f"sortie illisible ignorée (« {raw[:30]}… »)"
    # (les pointillés et soulignements des lignes vides du formulaire ne comptent pas)
    compact = text.replace(" ", "")
    if re.search(r"([^\s\._…\-/0-9٠-٩])\1{7,}", compact) or re.search(r"([0-9٠-٩])\1{14,}", compact):
        return "", f"répétition ignorée (« {raw[:30]}… »)"
    if re.search(r"[a-zA-Z]{4,}", text) and re.search(r"\b(wife|the|of|and|is|future|name)\b", text, re.I):
        return "", f"traduction inventée ignorée (« {raw[:30]}… »)"
    return text, ""


def posterior(scores, chosen):
    """Part de probabilité des candidats `chosen` parmi tous les candidats notés (softmax des
    log-probabilités). Mesure à quel point le choix l'emporte sur les autres possibilités :
    une valeur choisie dans une liste peut être sûre même si sa probabilité brute est faible
    (écriture difficile), tant qu'aucune autre valeur n'est proche."""
    if not scores:
        return 0.0
    top = max(scores.values())
    total = sum(math.exp(s - top) for s in scores.values())
    return sum(math.exp(scores[k] - top) for k in set(chosen) if k in scores) / total


def is_ditto(text):
    return bool(text) and re.fullmatch(r"[\"'“”„‟″〃/\\|،,`´ʺ״\s]+", text) is not None and len(text.strip()) <= 4


# ---------------------------------------------------------------- géométrie
def grow(box, image, dx=14, dy=6):
    x0, y0, x1, y1 = box
    return (max(0, x0 - dx), max(0, y0 - dy), min(image.width, x1 + dx), min(image.height, y1 + dy))


def clean_cell(page, box, height=160):
    """Case sans les traits du tableau, fond blanchi, encre foncée, agrandie.
    Aide le modèle sur l'écriture manuscrite (mesuré : « محمد الحايد » -> « مريم … »)."""
    x0, y0, x1, y1 = grow(box, page, dx=10, dy=6)
    gray = np.array(page.crop((x0, y0, x1, y1)).convert("L"))
    background = cv2.medianBlur(gray, 31).astype(np.float32) + 1
    flat = np.clip(gray.astype(np.float32) / background * 255, 0, 255).astype(np.uint8)
    ink = cv2.adaptiveThreshold(flat, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    h, w = ink.shape
    lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (int(0.6 * w), 1)))
    lines |= cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(0.6 * h))))
    flat[cv2.dilate(lines, np.ones((3, 3), np.uint8)) > 0] = 255
    flat = cv2.normalize(flat, None, 0, 255, cv2.NORM_MINMAX)
    image = Image.fromarray(flat).convert("RGB")
    return image.resize((max(1, int(image.width * height / image.height)), height), Image.LANCZOS)


def looks_like_arrow(image, box, margin=6):
    """Trait vertical seul dans la cellule (flèche « idem » dessinée à la main)."""
    x0, y0, x1, y1 = box
    crop = np.array(image.crop((x0 + margin, y0 + margin, x1 - margin, y1 - margin)).convert("L"))
    binary = binarize(crop)
    h, w = binary.shape
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, int(0.7 * w)), 1)))
    binary = cv2.subtract(binary, horiz)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ys, xs = np.nonzero(binary)
    if len(xs) < 20:
        return False
    bw, bh = xs.max() - xs.min(), ys.max() - ys.min()
    return bh > 0.55 * h and bw < 0.18 * w


# ---------------------------------------------------------------- partie haute
def read_upper(ocr, page, top, bottom, strip_height=300, overlap=90, log=print):
    strips, lines, texts = [], [], []
    y = top
    while y < bottom - 20:
        box = (0, y, page.width, min(bottom, y + strip_height))
        crop = page.crop(box)
        result = ocr.read(crop, PROMPT_LINES, max_new_tokens=220)
        strips.append((box, crop))
        texts.append(result.text)
        log(f"  bande y={y}: {len(result.lines)} lignes (confiance {result.conf:.2f})")
        for text, conf in result.lines:
            merge_line(lines, text, conf)
        if box[3] >= bottom:
            break
        y += strip_height - overlap
    return strips, lines, texts


def choose_grade(ocr, fields, strips, texts, log=print):
    """Champ « الرتبة » : on reprend la lecture de la bande jusqu'au libellé, puis le modèle
    note chaque grade connu comme suite du texte. Le meilleur remplace la lecture libre s'il
    n'est pas beaucoup moins probable qu'elle."""
    for f in fields:
        if f["label"] != "الرتبة" or not f["value"]:
            continue
        for (_, crop), text in zip(strips, texts):
            match = re.search(r"الرتب[ةه]\s*:", text)
            if not match:
                continue
            own = text[match.end():].split("\n")[0].rstrip()
            if not own.strip():
                continue
            candidates = [" " + g for g in GRADES]
            scores = ocr.score_candidates(crop, PROMPT_LINES, candidates + [own], prefix=text[:match.end()])
            best = max(candidates, key=scores.get)
            log(f"  grade : lu « {own.strip()} » ({scores[own]:.2f}), meilleur grade connu "
                f"« {best.strip()} » ({scores[best]:.2f})")
            if scores[best] >= scores[own] - GRADE_MARGIN:
                f["note"] = (f["note"] + " ; " if f["note"] else "") + \
                    f"choisi parmi les grades connus (lu : « {f['value']} »)"
                f["value"] = best.strip()
                # Confiance : probabilité du grade entier (suivi de la fin de ligne) parmi les grades connus
                full = ocr.score_candidates(crop, PROMPT_LINES, candidates, prefix=text[:match.end()], complete="\n")
                f["conf"] = posterior(full, [best])
            break


def merge_line(lines, text, conf):
    """Ajoute une ligne en supprimant les doublons dus au chevauchement des bandes."""
    if text.startswith("<img"):
        return
    text = sanitize(text)[0]
    if not clean_value(text):
        return
    if re.search(r"[Ͱ-ϿЀ-ӿ]", text):  # ni grec ni cyrillique dans ces formulaires : lettre mal lue
        conf = min(conf, FOREIGN_SCRIPT_CONF)
    for index in range(max(0, len(lines) - 8), len(lines)):
        old_text, old_conf = lines[index]
        if similar(old_text, text) >= 0.72 or (norm(text) and norm(text) in norm(old_text)):
            # On garde la version la plus complète (plus de contenu après les deux-points)
            if len(clean_value(text.split(":", 1)[-1])) > len(clean_value(old_text.split(":", 1)[-1])):
                lines[index] = (text, max(conf, old_conf))
            return
        if norm(old_text) and norm(old_text) in norm(text):
            lines[index] = (text, conf)
            return
    lines.append((text, conf))


def canonical_label(label):
    best, score = label, 0.0
    for known in KNOWN_LABELS:
        s = similar(label, known)
        if s > score:
            best, score = known, s
    return best if score >= 0.75 else label


def split_line(text):
    """« libellé 1 : ……… libellé 2 : ……… » sur une même ligne -> deux segments."""
    return [part for part in re.split(r"(?<=[\.…_]{3})\s*(?=[^\.…_:]{3,}:)", text) if part.strip()]


def parse_fields(lines):
    fields = []
    for text, conf in [(part, conf) for text, conf in lines for part in split_line(text)]:
        note = ""
        if ":" in text:
            label, value = text.split(":", 1)
            label, value = label.strip(" -–•"), clean_value(value)
        else:
            # « رقم الانخراط 005499 » : libellé suivi directement d'un numéro
            match = re.match(r"^(\D{3,}?)\s*(\d[\d\s/\-]*)$", text)
            if match and canonical_label(match.group(1).strip()) in KNOWN_LABELS:
                label, value = match.group(1).strip(), match.group(2).strip()
            elif canonical_label(clean_value(text.replace("=", " "))) in KNOWN_LABELS:
                # Libellé seul (valeur vide ou écrite ailleurs, ex. dans une case au-dessus)
                label, value = clean_value(text.replace("=", " ")), ""
            else:
                label, value = "Texte libre", clean_value(text)
        canon = canonical_label(label) if label != "Texte libre" else label
        if label != "Texte libre" and not value and canon not in KNOWN_LABELS:
            # « Carte de Soin (…) 0000 02102 : ______ » : la donnée est avant les deux-points
            label = canon = "Texte libre"
            value = clean_value(text.split(":", 1)[0])
        if canon != label:
            note = f"libellé lu : « {label} »"
        if "تاريخ" in canon or "date" in canon.lower():
            date = normalize_date(value)
            if date and date != value:
                note = (note + " ; " if note else "") + f"date normalisée (lu : « {value} »)"
                rest = re.sub(r"[\d\s/\-–]+", " ", value).strip(" -–")
                value = date + (f" — {rest}" if rest else "")
            if impossible_date(value):
                note = (note + " ; " if note else "") + "date impossible : un chiffre est mal lu"
                conf = min(conf, 0.4)
        fields.append({"label": canon, "value": value, "conf": conf, "note": note, "raw": text})
    return attach_boxed_numbers(fields)


def attach_boxed_numbers(fields):
    """« رقم … » imprimé sous une case : le numéro écrit dans la case est lu sur une ligne
    précédente, souvent collé à un autre texte. On le rattache au libellé resté vide.
    (Pas plus de 2 lignes au-dessus : plus haut, c'est un autre numéro de la page, ex.
    « 80041685 » en haut à droite ; les cases encadrées sont relues par read_number_boxes.)"""
    for index, f in enumerate(fields):
        if f["value"] or "رقم" not in f["label"]:
            continue
        for prev in range(index - 1, max(-1, index - 3), -1):
            other = fields[prev]
            if other["label"] != "Texte libre":
                continue
            # chiffres d'une case à cocher parfois lus séparés (« 8 0 0 4 1 6 8 5 »)
            match = re.search(r"(?<!\d)(\d(?:\s?\d){4,})(?!\d)", other["value"])
            if not match:
                continue
            f["value"] = re.sub(r"\s", "", match.group(1))
            f["conf"] = min(f["conf"], other["conf"]) if f["conf"] else other["conf"]
            f["note"] = (f["note"] + " ; " if f["note"] else "") + "numéro lu dans la case au-dessus du libellé"
            other["value"] = clean_value(other["value"].replace(match.group(1), " "))
            break
    kept = []
    for f in fields:
        if not f["value"] and (f["label"] == "Texte libre" or any(
                k["label"] == f["label"] and not k["value"] for k in kept[-2:])):
            continue  # vide, ou libellé vide répété (chevauchement des bandes)
        kept.append(f)
    return kept


def read_number_boxes(ocr, page, bottom, fields, log=print):
    """Numéros écrits dans une case encadrée, libellé imprimé sous la case (« الرقم الموحد »).
    La lecture par bandes mélange la case avec le texte voisin (mesuré : « 80041685 », écrit en
    haut à droite, pris pour le numéro unifié « 0000000000 ») : on relit la case seule, en deux
    moitiés coupées entre deux chiffres. D'un seul tenant, le modèle compte mal une longue suite
    de zéros (9 lus pour 10) ; sur 4 à 6 chiffres il ne se trompe plus de nombre."""
    for box in find_boxes(page, bottom):
        if ink_ratio(page, box) < INK_THRESHOLD:
            continue  # case vide : inutile de lire son libellé
        x0, y0, x1, y1 = box
        below = (max(0, x0 - 40), y1, min(page.width, x1 + 40), min(page.height, y1 + int(0.9 * (y1 - y0))))
        label = canonical_label(clean_value(sanitize(ocr.read(page.crop(below), PROMPT_HEADER, 30).text)[0]))
        if label not in KNOWN_LABELS or "رقم" not in label:
            continue
        if crossed_out(page, box):
            # (le modèle y invente « 123456789 »)
            log(f"  case encadrée « {label} » : barrée, ignorée")
            continue
        cut = middle_gap(page, box)
        reads = [ocr.read(page.crop((a - 2, y0 - 4, b + 2, y1 + 4)), PROMPT_NUMBER, 20)
                 for a, b in ((x0, cut), (cut, x1))]
        texts = [sanitize(r.text)[0] for r in reads]
        log(f"  case encadrée « {label} » : " + " | ".join(f"« {r.text} » ({r.conf:.2f})" for r in reads))
        # « o » / « O » écrits pour des zéros dans une suite de chiffres
        if not all(re.fullmatch(r"[\d\soO]+", t) for t in texts):
            continue
        digits = re.sub(r"\D", "", re.sub(r"[oO]", "0", "".join(texts)))
        if len(digits) < 5:
            continue
        conf = min(r.conf for r in reads)
        note = f"lu dans la case encadrée au-dessus du libellé (lu : « {' | '.join(r.text for r in reads)} »)"
        if conf < NUMBER_SURE_CONF:
            note += " ; chiffre peu lisible (rature, trait par-dessus) : à vérifier"
        f = next((f for f in fields if f["label"] == label), None)
        if f is None:
            fields.insert(0, {"label": label, "value": digits, "conf": conf, "note": note, "raw": "".join(texts)})
            continue
        if f["value"] and f["value"] != digits:
            note += f" ; lecture de la ligne écartée : « {f['value']} »"
        f.update(value=digits, conf=conf, note=note)


# ---------------------------------------------------------------- tableau
def column_kind(header):
    h = norm(header)
    if "اسم" in h or "nom" in h:
        return "name"
    if "تاريخ" in h or "date" in h or "ولاده" in h:
        return "date"
    return "text"


def read_table(ocr, page, table, family_hint="", log=print):
    n_cols = table.n_cols
    # Colonne des numéros de ligne : la plus étroite sur un bord du tableau
    widths = [table.col_lines[c + 1] - table.col_lines[c] for c in range(n_cols)]
    number_col = n_cols - 1 if widths[-1] <= widths[0] else 0

    # En-têtes (ligne 0) : une cellule fusionnée couvre plusieurs colonnes,
    # numérotées dans le sens de lecture (de droite à gauche si N° est à droite)
    rtl = number_col == n_cols - 1
    headers = [""] * n_cols
    header_cells = [b for b in table.row_boxes[0]] if table.row_boxes else []
    for box in header_cells:
        covered = [c for c in range(n_cols)
                   if min(box[2], table.col_lines[c + 1]) - max(box[0], table.col_lines[c])
                   > 0.5 * widths[c]]
        if not covered:
            continue
        text = ""
        if ink_ratio(page, box) >= INK_THRESHOLD:
            read = ocr.read(page.crop(grow(box, page)), PROMPT_HEADER, 40)
            text, _ = sanitize(read.text)
            text = clean_value(text) if read.conf >= 0.6 else ""
        for i, c in enumerate(covered):
            index = len(covered) - i if rtl else i + 1
            headers[c] = text if len(covered) == 1 else f"{text} ({index})" if text else ""
    headers[number_col] = "N°"
    for c in range(n_cols):
        if not headers[c]:
            headers[c] = f"Colonne {n_cols - c if rtl else c + 1}"
    kinds = [column_kind(h) for h in headers]
    kinds[number_col] = "number"
    log(f"  en-têtes : {headers}")
    # Colonne « lien de parenté » : juste après la date de naissance dans le sens de lecture
    date_cols = [c for c in range(n_cols) if kinds[c] == "date"]
    relation_col = None
    if date_cols:
        relation_col = date_cols[0] - 1 if rtl else date_cols[0] + 1
        if not 0 <= relation_col < n_cols or kinds[relation_col] != "text":
            relation_col = None

    rows, hypotheses, clean_images, readings = [], {}, {}, {}
    for r in range(1, table.n_rows):
        cells = []
        for c in range(n_cols):
            box = table.cells.get((r, c))
            if box is None:
                cells.append(Cell(r, c, None))
                continue
            cell = Cell(r, c, box, image=page.crop(grow(box, page)))
            cells.append(cell)
            if c == number_col:
                cell.text = str(r)
                continue
            if ink_ratio(page, box) < INK_THRESHOLD:
                continue
            if looks_like_arrow(page, box):
                cell.text, cell.raw, cell.note = ARROW, ARROW, "flèche : même valeur que les lignes au-dessus"
                continue
            prompt = {"name": PROMPT_NAME, "date": PROMPT_DATE}.get(kinds[c], PROMPT_CELL)
            # Lecture directe (la plus fiable dans nos tests), confiance = probabilité moyenne des tokens
            read = ocr.read(cell.image, prompt, 40)
            if kinds[c] == "name":
                # La consigne « nom arabe » pousse parfois le modèle à inventer un nom
                # (ex. « عبد الله » pour « ordre ») ; l'image nettoyée aide sur l'écriture
                # difficile. On garde la lecture la plus sûre.
                clean = clean_images[(r, c)] = clean_cell(page, box)
                readings[(r, c)] = [read.text]
                for image, other_prompt in ((cell.image, PROMPT_CELL), (clean, PROMPT_NAME), (clean, PROMPT_CELL)):
                    other = ocr.read(image, other_prompt, 40)
                    readings[(r, c)].append(other.text)
                    if other.conf > read.conf and sanitize(other.text)[0]:
                        read = other
            cell.raw = read.text
            cell.text, cell.note = sanitize(read.text)
            cell.conf = read.conf if cell.text else 0.0
            # Petite marque isolée (bout de flèche, point) : on ne la garde pas
            if len(cell.text) == 1 and not cell.text.isdigit() and not is_ditto(cell.text) and read.conf < 0.6:
                cell.text, cell.note = "", f"marque isolée ignorée (« {read.text} »)"
            if c == relation_col and cell.text and read.conf < RELATION_MAX_CONF and re.search(r"[؀-ۿ]", cell.text):
                above = rows[-1][c].text if rows else ""
                choose_relation(ocr, cell, above)
                log(f"    lien de parenté ligne {r} : « {cell.raw} » -> « {cell.text} »")
            # Colonne « nom » : hypothèses supplémentaires pour le vote du nom de famille
            if cell.text and kinds[c] == "name":
                hypotheses[(r, c)] = [(cell.text, math.log(max(read.conf, 1e-6)))] + ocr.read_hypotheses(
                    cell.image, prompt, n=4)
                readings[(r, c)] += [text for text, _ in hypotheses[(r, c)][1:]]
        if any(cell.text for cell in cells if cell.col != number_col):
            rows.append(cells)
            log(f"  ligne {r} : " + " | ".join(cell.text for cell in cells if cell.text))
    promote_subheaders(rows, headers, number_col, log=log)
    postprocess_table(rows, kinds, hypotheses, number_col)
    name_cols = [c for c in range(n_cols) if kinds[c] == "name"]
    if name_cols and relation_col is not None:
        match_gender(rows, name_cols[0], relation_col)
    if relation_col is not None:
        check_relation_vocab(rows, relation_col)
    family = None
    for c in name_cols:
        family = harmonize_family(ocr, rows, c, hypotheses, clean_images, readings, family_hint, log=log) or family
    return headers, rows, family


def promote_subheaders(rows, headers, number_col, log=print):
    """Sous-titres écrits dans la ligne 1 sous un en-tête fusionné ou illisible
    (« Validité », « Oui/Non » sous « ملاحظات ») : texte en ligne 1 seulement, cases vides
    en dessous. Ce sont des titres de colonnes, pas des données : on les met dans l'en-tête.
    Au moins deux colonnes, sinon une seule valeur de la ligne 1 pourrait être prise pour un titre."""
    if len(rows) < 2 or rows[0][number_col].text != "1":
        return
    cols = [c for c, cell in enumerate(rows[0])
            if c != number_col and cell.text and cell.text not in (DITTO, ARROW)
            and (headers[c].startswith("Colonne ") or headers[c].endswith(")"))
            and not any(cells[c].text for cells in rows[1:])]
    if len(cols) < 2:
        return
    for c in cols:
        cell = rows[0][c]
        base = re.sub(r"\s*\(\d+\)$", "", headers[c])
        headers[c] = cell.text if base.startswith("Colonne ") else f"{base} : {cell.text}"
        cell.text, cell.conf, cell.note = "", 1.0, ""
    log(f"  sous-titres de la ligne 1 passés dans l'en-tête : {[headers[c] for c in cols]}")


def choose_relation(ocr, cell, above=""):
    """Lecture peu sûre dans la colonne « lien de parenté » : le modèle note chaque mot connu
    sachant l'image, et on garde le meilleur s'il n'est pas beaucoup moins probable que la
    lecture libre (mesuré : « الذي » -> المنخرط, « الإس 1 » -> الابن 1, « المنزل » -> الابن/البنت 2)."""
    numbers = set(re.findall(r"\d+", cell.text))
    match = re.fullmatch(r"(الابن|البنت) (\d+)", above or "")
    if match:
        numbers.add(str(int(match.group(2)) + 1))
    candidates = list(RELATION_WORDS) + [f"{w} {n}" for n in sorted(numbers) for w in ("الابن", "البنت")]
    scores = ocr.score_candidates(cell.image, PROMPT_CELL, candidates + [cell.text])
    free = scores.get(cell.text)
    best = max(candidates, key=lambda w: scores.get(w, -99))
    if free is None or scores.get(best, -99) < free - RELATION_MARGIN or best == cell.text:
        return
    cell.note = (f"choisi parmi les liens de parenté connus (lu : « {cell.text} », "
                 f"probabilité {math.exp(scores[best]):.0%} contre {math.exp(free):.0%})")
    # La lecture libre est écartée (mot inconnu) : la confiance compare les seuls mots connus,
    # chacun noté comme réponse entière (sinon « المنخرط » et « المنخرطة » se partagent la note)
    cell.text, cell.scores = best, ocr.score_candidates(cell.image, PROMPT_CELL, candidates, complete=END)
    cell.conf = relation_conf(cell.scores, best)


def relation_word(text):
    return re.sub(r"[\d\s]+", "", text)


def relation_conf(scores, text, words=()):
    """Confiance d'un lien de parenté choisi dans la liste : part de probabilité du mot retenu
    (avec ou sans numéro, « الابن » et « الابن 1 » se répartissent la même lecture)."""
    words = {relation_word(text), *words}
    return posterior(scores, [k for k in scores if relation_word(k) in words])


def name_gender(name):
    first = norm(name.split()[0]) if name.split() else ""
    if any(norm(n) == first for n in FEMALE_NAMES):
        return "f"
    if any(norm(n) == first for n in MALE_NAMES):
        return "m"
    return None


def match_gender(rows, name_col, relation_col, max_conf=0.8):
    """Lien de parenté peu sûr dont le genre contredit le prénom de la ligne : on prend
    l'autre forme (الزوج <-> الزوجة, الابن <-> البنت…). Une lecture sûre n'est jamais modifiée."""
    to_female = GENDER_PAIRS
    to_male = {f: m for m, f in GENDER_PAIRS.items()}
    for cells in rows:
        name, relation = cells[name_col], cells[relation_col]
        if not relation.text or (relation.scores is None and relation.conf >= max_conf):
            continue
        gender = name_gender(name.text)
        word, _, number = relation.text.partition(" ")
        swap = to_female.get(word) if gender == "f" else to_male.get(word) if gender == "m" else None
        if swap:
            relation.note = (relation.note + " ; " if relation.note else "") + \
                f"accordé avec le prénom « {name.text.split()[0]} » (lu : « {relation.text} »)"
            relation.text = f"{swap} {number}".strip()
        pair = to_female.get(relation_word(relation.text)) or to_male.get(relation_word(relation.text))
        if gender and pair and relation.scores:
            # Le prénom tranche entre les deux formes : l'image n'a plus qu'à désigner le mot
            # (ex. الزوج / الزوجة), le prénom confirme la forme (liste de prénoms, rarement fausse)
            relation.conf = 0.95 * relation_conf(relation.scores, relation.text, {pair})


def harmonize_family(ocr, rows, col, hypotheses, clean_images, readings, hint="", log=print):
    """Nom de famille commun aux lignes du tableau. Chaque nom candidat (dernier mot des lectures
    de chaque ligne et du champ « الاسم الإداري الكامل ») est noté par le modèle sur l'image de
    chaque ligne ; la somme sur toutes les lignes désigne le nom le plus probable pour la famille.
    Une ligne n'est modifiée que si ce nom est presque aussi probable que sa propre lecture
    (une épouse peut garder son nom)."""
    arabic = [cells[col] for cells in rows
              if re.search(r"[؀-ۿ]", cells[col].text) and (cells[col].row, col) in clean_images]
    named = [cell for cell in arabic if len(cell.text.split()) >= 2]
    if len(named) < 2:
        return None
    candidates = {cell.text.split()[-1] for cell in named} | ({hint} if hint else set())
    for cell in named:
        candidates |= {text.split()[-1] for text, _ in hypotheses.get((cell.row, col), []) if len(text.split()) >= 2}
    candidates = sorted(c for c in candidates if len(norm(c)) >= 3 and re.search(r"[؀-ۿ]", c))
    scores = {cell.row: ocr.score_candidates(clean_images[(cell.row, col)], PROMPT_FAMILY, candidates)
              for cell in arabic}
    total = {c: sum(scores[cell.row][c] for cell in named) for c in candidates}
    family = max(total, key=total.get)
    log("  nom de famille : " + ", ".join(f"{c} ({total[c]:.1f})" for c in sorted(total, key=total.get,
                                                                               reverse=True)[:4]))
    worst = min(scores[cell.row][family] for cell in named)
    # Toutes les lignes votent : le nom de famille est sûr s'il l'emporte nettement sur l'ensemble
    # (« الحاج » est noté sans fin de mot : c'est le début de « الحاجب », pas un concurrent)
    family_like = [c for c in candidates if family.startswith(c)]
    family_conf = posterior(total, family_like)
    for cell in arabic:
        words, s = cell.text.split(), scores[cell.row]
        trust = family_conf
        if len(words) == 1:
            # le modèle n'a lu que le prénom : on ajoute le nom de famille s'il colle à l'image
            if s[family] >= worst - FAMILY_MARGIN and len(cell.text) <= 8:
                cell.note = f"nom de famille ajouté d'après les autres lignes (lu : « {cell.text} »)"
                cell.text = f"{cell.text} {family}"
                trust = min(trust, posterior(s, family_like))
        elif words[-1] != family and s[family] >= s.get(words[-1], -99) - FAMILY_MARGIN:
            cell.note = f"nom de famille harmonisé avec les autres lignes (lu : « {cell.text} »)"
            cell.text = " ".join(words[:-1] + [family])
            # Nom remplacé par le vote des autres lignes : l'image de cette ligne doit aussi le désigner
            # (mesuré : « الحادي » lu partout, « الحاجي » voté, alors que deux lignes portaient « الحاير »)
            trust = min(trust, posterior(s, family_like))
        elif words[-1] != family:
            cell.note = f"nom de famille différent des autres lignes ({family}) : à vérifier"
            cell.conf = min(cell.conf, 0.5)
            continue
        if cell.text.split()[-1] == family:
            # Confiance = prénom x nom de famille (vote). Le prénom retenu est comparé aux autres
            # prénoms proposés par les différentes lectures de la case, notés sur l'image nettoyée
            first = cell.text.split()[0]
            # (nom complet noté jusqu'à la fin de la réponse : un prénom tronqué ne compte pas)
            names = {r.split()[0] for r in readings.get((cell.row, col), []) if re.search(r"[؀-ۿ]", r)} | {first}
            # + prénoms connus qui ressemblent au prénom lu : si les lectures se répètent (« أسامة » x4),
            # seuls de vrais concurrents (« أسماء », « ناجح » pour « ناجع ») montrent que l'écriture est
            # ambiguë ; des prénoms sans rapport (« نزار ») ne feraient que diluer la confiance
            names |= {n for n in FEMALE_NAMES | MALE_NAMES
                      if norm(n)[:1] == norm(first)[:1] and similar(n, first) >= NAME_RIVAL}
            s1 = ocr.score_candidates(clean_images[(cell.row, col)], PROMPT_NAME,
                                      [f"{n} {family}" for n in sorted(names)], complete=END)
            cell.conf = posterior(s1, [f"{first} {family}"]) * trust
    return family, family_conf


def check_relation_vocab(rows, relation_col):
    """Colonne « lien de parenté » : un mot hors vocabulaire n'est jamais affiché comme sûr, même
    lu avec une forte probabilité (mesuré : « الدين » lu à 0.98 pour « الادين » / « الدبن » écrits)."""
    known = {norm(w) for w in RELATION_WORDS}
    for cells in rows:
        cell = cells[relation_col]
        if cell.text and cell.text not in (DITTO, ARROW) and norm(relation_word(cell.text)) not in known:
            cell.conf = min(cell.conf, UNKNOWN_RELATION_CONF)
            cell.note = (cell.note + " ; " if cell.note else "") + "mot hors des liens de parenté connus : à vérifier"


def reconcile_full_name(fields, family, family_conf):
    """Nom de famille du champ « الاسم الإداري الكامل » lu une seule fois, contre le vote de toutes
    les lignes du tableau : une variante proche (« الحامي » / « الحاجي ») prend le nom voté."""
    for f in fields:
        words = f["value"].split()
        if f["label"] != "الاسم الإداري الكامل" or len(words) < 2 or words[-1] == family:
            continue
        if similar(words[-1], family) >= 0.6:
            f["note"] = (f["note"] + " ; " if f["note"] else "") + \
                f"nom de famille aligné sur le tableau (lu : « {f['value']} »)"
            f["value"] = " ".join(words[:-1] + [family])
            f["conf"] = min(f["conf"], family_conf)
        else:
            f["note"] = (f["note"] + " ; " if f["note"] else "") + \
                f"nom de famille différent du tableau ({family}) : à vérifier"
            f["conf"] = min(f["conf"], 0.5)


def postprocess_table(rows, kinds, hypotheses, number_col):
    # 1) Guillemets de répétition : on recopie la valeur de la ligne du dessus
    for index, cells in enumerate(rows):
        for cell in cells:
            if cell.col == number_col or not cell.text:
                continue
            if is_ditto(cell.text) or (kinds[cell.col] == "date" and is_ditto(cell.raw)):
                above = next((rows[i][cell.col].text for i in range(index - 1, -1, -1)
                              if rows[i][cell.col].text and rows[i][cell.col].text != DITTO), "")
                cell.note = f"{DITTO} = même valeur qu'au-dessus" + (f" ({above})" if above else "")
                cell.text = DITTO
                cell.conf = max(cell.conf, 0.9)
            elif kinds[cell.col] == "date":
                if re.fullmatch(r"[0-9oO/\-\. ]+", cell.text) and re.search(r"[oO]", cell.text):
                    cell.note = f"lettres « o » remplacées par des zéros (lu : « {cell.text} »)"
                    cell.text = re.sub(r"[oO]", "0", cell.text)
                date = normalize_date(cell.text)
                if date and date != cell.text:
                    cell.note = f"date normalisée (lu : « {cell.text} »)"
                    cell.text = date
                if impossible_date(cell.text):
                    cell.note = (cell.note + " ; " if cell.note else "") + "date impossible : un chiffre est mal lu"
                    cell.conf = min(cell.conf, 0.4)

    # 2) Vocabulaire des liens de parenté (colonnes texte en arabe)
    for cells in rows:
        for cell in cells:
            if kinds[cell.col] != "text" or not cell.text or cell.text in (DITTO, ARROW):
                continue
            best_word, best_score, best_digit = None, 0.0, ""
            for candidate in [cell.text]:
                digit = re.search(r"\d+", candidate)
                word = re.sub(r"[\d\s]+", "", candidate)
                for known in RELATION_WORDS:
                    s = similar(word, known)
                    if s > best_score:
                        best_word, best_score, best_digit = known, s, digit.group() if digit else ""
            if best_word and best_score >= 0.7:
                corrected = f"{best_word} {best_digit}".strip()
                if corrected != cell.text:
                    cell.note = f"corrigé avec le vocabulaire des liens de parenté (lu : « {cell.text} »)"
                    cell.text = corrected


# ---------------------------------------------------------------- point d'entrée
def read_form(ocr, path, log=print, source=None):
    """path : chemin de l'image ou image PIL déjà ouverte (une page d'un PDF)."""
    start = time.time()
    page = deskew(straighten_page(load_image(path)))
    result = FormResult(source=source or str(path), page=page)
    table = detect_table(page)
    top_of_table = table.box[1] - 6 if table else page.height
    log(f"Tableau : {'trouvé, %d lignes x %d colonnes' % (table.n_rows, table.n_cols) if table else 'aucun'}")
    log("Lecture de la partie haute...")
    result.strips, result.raw_lines, texts = read_upper(ocr, page, 0, top_of_table, log=log)
    result.fields = parse_fields(result.raw_lines)
    read_number_boxes(ocr, page, top_of_table, result.fields, log=log)
    choose_grade(ocr, result.fields, result.strips, texts, log=log)
    if table:
        log("Lecture du tableau cellule par cellule...")
        full_name = next((f["value"] for f in result.fields if f["label"] == "الاسم الإداري الكامل"), "")
        hint = full_name.split()[-1] if len(full_name.split()) >= 2 else ""
        result.headers, result.rows, family = read_table(ocr, page, table, hint, log=log)
        if family:
            reconcile_full_name(result.fields, *family)
    result.seconds = time.time() - start
    return result


def merge_pages(results):
    """Document de plusieurs pages : champs et texte de toutes les pages, tableau le plus grand.
    La page gardée pour l'affichage est celle du tableau (ou la première)."""
    if len(results) == 1:
        return results[0]
    main = max(results, key=lambda r: len(r.rows))
    merged = FormResult(source=results[0].source, page=main.page, headers=main.headers, rows=main.rows,
                        seconds=sum(r.seconds for r in results))
    for number, result in enumerate(results, start=1):
        for f in result.fields:
            merged.fields.append({**f, "note": (f["note"] + " ; " if f["note"] else "") + f"page {number}"})
        merged.raw_lines += result.raw_lines
        merged.strips += result.strips
    return merged
