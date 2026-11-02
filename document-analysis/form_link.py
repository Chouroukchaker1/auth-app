"""Conversion du résultat d'analyse vers les champs du formulaire adhérent (Angular).

Les libellés sont reconnus en arabe ou en français, même mal lus (comparaison approchée) :
un autre modèle de formulaire remplit donc les mêmes champs s'il porte des libellés proches.
"""
import re

from form_reader import ARROW, DITTO, column_kind, is_ditto, norm, normalize_date, similar

MESSAGE_TYPE = "nanonets-ocr/member-form"
LABEL_MATCH = 0.8  # ressemblance minimale entre un libellé lu et un libellé connu

# Champ du formulaire adhérent -> libellés possibles sur un document (arabe et français)
FIELD_LABELS = {
    "nomPrenom": ["الاسم الإداري الكامل", "الاسم واللقب", "الاسم و اللقب", "الإسم واللقب", "الاسم الكامل",
                  "Nom et prénom", "Nom et prénoms", "Nom complet", "Nom prénom"],
    "numeroAffiliation": ["رقم الانخراط", "رقم الاشتراك", "عدد الانخراط", "Numéro d'affiliation",
                          "N° d'affiliation", "N° affiliation", "Numéro d'adhésion", "N° adhérent"],
    "numeroUnifie": ["الرقم الموحد", "الرقم المعتمد", "المعرف الوحيد", "Numéro unifié", "N° unifié",
                     "Identifiant unique"],
    "grade": ["الرتبة", "Grade"],
    "naissance": ["تاريخ ومكان الولادة", "تاريخ و مكان الولادة", "Date et lieu de naissance"],
    "dateNaissance": ["تاريخ الولادة", "Date de naissance", "Né le", "Née le"],
    "lieuNaissance": ["مكان الولادة", "Lieu de naissance"],
    "debutActivite": ["تاريخ مباشرة العمل", "تاريخ الانتداب", "انطلاق العمل", "Début de l'activité",
                      "Date de recrutement", "Date d'entrée en fonction", "Date de début"],
    "dateMariage": ["تاريخ عقد الزواج", "تاريخ الزواج", "Date du mariage", "Date de mariage"],
}
DATE_KEYS = {"debutActivite", "dateMariage", "dateNaissance"}
DIGIT_KEYS = {"numeroAffiliation", "numeroUnifie"}

# Lien de parenté lu (arabe ou français) -> valeur du champ « lienParente » (vide : à choisir à la main)
RELATIONS = {
    "الزوجة": "epouse", "الزوج": "epoux", "الابن": "fils", "الابنة": "fille", "البنت": "fille",
    "الأب": "", "الأم": "", "المنخرط": "self", "المنخرطة": "self",
    "épouse": "epouse", "femme": "epouse", "époux": "epoux", "mari": "epoux", "fils": "fils", "fille": "fille",
    "père": "", "mère": "", "adhérent": "self", "adhérente": "self",
}

MONTHS = {
    # français
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
    # arabe (Maghreb puis Machrek)
    "جانفي": 1, "فيفري": 2, "مارس": 3, "أفريل": 4, "افريل": 4, "ماي": 5, "جوان": 6, "جويلية": 7, "أوت": 8,
    "اوت": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12, "يناير": 1, "فبراير": 2,
    "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
}
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def field_key(label):
    """Champ du formulaire correspondant à un libellé lu (None si aucun ne ressemble assez)."""
    best, score = None, 0.0
    for key, labels in FIELD_LABELS.items():
        for known in labels:
            s = 1.0 if norm(label) == norm(known) else similar(label, known)
            if s > score:
                best, score = key, s
    return best if score >= LABEL_MATCH else None


def iso_date(text):
    """Date complète AAAA-MM-JJ, sinon chaîne vide (dates partielles « 0000/.. » ignorées).
    Accepte aussi les chiffres arabes et les mois en lettres (« 10 octobre 1980 », « 10 أكتوبر 1980 »)."""
    text = (text or "").translate(ARABIC_DIGITS)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    date = match.group() if match else normalize_date(text)
    if not date:
        month = next((number for name, number in MONTHS.items() if re.search(rf"(?<!\w){name}(?!\w)", text.lower())),
                     None)
        day_year = re.search(r"(?<!\d)(\d{1,2})\D+?(\d{4})(?!\d)", text)
        if month and day_year:
            date = normalize_date(f"{day_year.group(1)}/{month}/{day_year.group(2)}")
    return date if date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else ""


def birth_place(text):
    place = re.sub(r"[\d/\-.٠-٩]+", " ", text)
    for name in MONTHS:
        place = re.sub(rf"(?<!\w){name}(?!\w)", " ", place, flags=re.I)
    return re.sub(r"\s+", " ", place).strip(" —-–،,")


def relation_of(text):
    """Lien de parenté connu le plus proche du texte lu (None si aucun ne ressemble assez)."""
    word = re.sub(r"[\d\s]+", "", text or "")
    best, score = None, 0.0
    for known in RELATIONS:
        s = similar(word, known)
        if s > score:
            best, score = known, s
    return best if score >= 0.7 else None


def read_fields(data):
    fields = {}
    for f in data["fields"]:
        key = field_key(f["label"]) if f["label"] != "Texte libre" else None
        value = (f["value"] or "").strip()
        if key and value and key not in fields:
            fields[key] = value
    result = {}
    if "nomPrenom" in fields:
        result["nomPrenom"] = fields["nomPrenom"]
    for key in DIGIT_KEYS & fields.keys():
        digits = re.sub(r"\D", "", fields[key].translate(ARABIC_DIGITS))
        if digits:
            result[key] = digits
    for key in DATE_KEYS & fields.keys():
        if iso_date(fields[key]):
            result[key] = iso_date(fields[key])
    if "grade" in fields:
        result["grade"] = fields["grade"]
    if "lieuNaissance" in fields:
        result["lieuNaissance"] = birth_place(fields["lieuNaissance"])
    if "naissance" in fields:
        # « 1980-10-10 — الحمامي » : date puis lieu
        birth = fields["naissance"]
        if iso_date(birth) and "dateNaissance" not in result:
            result["dateNaissance"] = iso_date(birth)
        if birth_place(birth) and "lieuNaissance" not in result:
            result["lieuNaissance"] = birth_place(birth)
    for f in data["fields"]:
        cnr = re.search(r"CNR[\s:\-]*(\d{4,10})", f"{f['value']} {f.get('raw', '')}".translate(ARABIC_DIGITS), re.I)
        if cnr:
            result["cnr"] = f"CNR-{cnr.group(1)}"
            break
    return {key: value for key, value in result.items() if value}


def read_family(data, adherent=""):
    """Une personne par ligne du tableau : nom, lien de parenté et date de naissance.
    La ligne de l'adhérent lui-même (« المنخرط », ou son prénom en première ligne) est écartée."""
    headers, rows = data["table"]["headers"], data["table"]["rows"]
    kinds = [column_kind(h) if h != "N°" else "number" for h in headers]
    name_col = next((c for c, k in enumerate(kinds) if k == "name"), None)
    date_col = next((c for c, k in enumerate(kinds) if k == "date"), None)
    if name_col is None:
        return [], ""
    # Colonne du lien de parenté : celle où le plus de cases sont un lien connu
    text_cols = [c for c, k in enumerate(kinds) if k == "text"]
    relation_col = max(text_cols, key=lambda c: sum(bool(relation_of(cells[c]["text"])) for cells in rows),
                       default=None)
    family, self_birth, previous_date = [], "", ""
    for cells in rows:
        name = cells[name_col]["text"].strip()
        date_text = cells[date_col]["text"].strip() if date_col is not None else ""
        if date_text == DITTO or date_text == "↓" or is_ditto(date_text):
            date = previous_date
        else:
            date = iso_date(date_text)
        previous_date = date
        relation = relation_of(cells[relation_col]["text"]) if relation_col is not None else None
        if not name or name == ARROW or is_ditto(name):
            continue
        lien = RELATIONS.get(relation, "")
        if lien == "self" or (not family and adherent and similar(name.split()[0], adherent.split()[0]) >= 0.7):
            self_birth = self_birth or date
            continue
        if not relation and not date and len(name.split()) < 2:
            continue  # mot isolé hors d'une vraie ligne (« ordre », bas du tableau)
        # Dans le formulaire : « الإسم » = premier mot, « اللقب » = le reste (nom de famille)
        first, _, last = name.partition(" ")
        family.append({"nom": first, "prenom": last, "lienParente": lien, "dateNaissance": date})
    return family, self_birth


def to_member_form(data):
    """Valeurs envoyées au formulaire adhérent (seules les valeurs effectivement lues)."""
    fields = read_fields(data)
    family, self_birth = read_family(data, fields.get("nomPrenom", ""))
    if self_birth and "dateNaissance" not in fields:
        fields["dateNaissance"] = self_birth
    return {"type": MESSAGE_TYPE, "source": data["source"], "fields": fields, "family": family}
