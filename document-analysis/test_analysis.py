"""Tests rapides, sans le modèle (lancés par Jenkins dans l'image) : python test_analysis.py"""
import io
import sys

from PIL import Image

import api  # noqa: F401  (le service se charge sans erreur)
from document import load_pages
from form_link import field_key, iso_date, relation_of, to_member_form


def test_labels():
    assert field_key("الاسم الإداري الكامل") == "nomPrenom"
    assert field_key("Nom et prénom") == "nomPrenom"
    assert field_key("رقم الانخراط") == "numeroAffiliation"
    assert field_key("Date de naissance") == "dateNaissance"
    assert field_key("ملاحظات") is None


def test_dates():
    assert iso_date("10 - 10 - 1980") == "1980-10-10"
    assert iso_date("10 octobre 1980") == "1980-10-10"
    assert iso_date("١٠/١٠/١٩٨٠") == "1980-10-10"
    assert iso_date("0000/00/00") == ""


def test_relations():
    assert relation_of("الزوجة") == "الزوجة"
    assert relation_of("Fils") == "fils"


def test_member_form():
    cell = lambda text: {"text": text, "conf": 0.9, "note": "", "raw": text}  # noqa: E731
    data = {
        "source": "test.png",
        "fields": [
            {"label": "الاسم الإداري الكامل", "value": "أحمد الحاجي", "conf": 0.9, "note": "", "raw": ""},
            {"label": "تاريخ ومكان الولادة", "value": "1980-10-10 — الحمامي", "conf": 0.9, "note": "", "raw": ""},
            {"label": "Texte libre", "value": "CNR 445566", "conf": 0.9, "note": "", "raw": ""},
        ],
        "table": {"headers": ["علاقة", "تاريخ الولادة", "الاسم", "N°"],
                  "rows": [[cell("الزوجة"), cell("1985-03-02"), cell("مريم الحاجي"), cell("1")]]},
    }
    result = to_member_form(data)
    assert result["fields"] == {"nomPrenom": "أحمد الحاجي", "dateNaissance": "1980-10-10",
                                "lieuNaissance": "الحمامي", "cnr": "CNR-445566"}, result["fields"]
    assert result["family"] == [{"nom": "مريم", "prenom": "الحاجي", "lienParente": "epouse",
                                 "dateNaissance": "1985-03-02"}], result["family"]


def test_documents():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, format="PNG")
    buffer.seek(0)
    assert len(load_pages(buffer)) == 1
    try:
        load_pages(io.BytesIO(b"pas une image"), check_only=True)
    except ValueError:
        pass
    else:
        raise AssertionError("un fichier invalide doit être refusé")


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"{len(tests)} tests réussis")
    sys.exit(0)
