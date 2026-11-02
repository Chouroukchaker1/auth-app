"""Export des résultats : Excel (avec images des cellules), PDF et JSON."""
import io
import json
import os
import re
import urllib.request
from html import escape
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

GOOD, MEDIUM = 0.80, 0.55
FILL_HEADER = PatternFill("solid", fgColor="DCE6F1")
FILL_MEDIUM = PatternFill("solid", fgColor="FFF2CC")
FILL_LOW = PatternFill("solid", fgColor="F8CBAD")
THIN = Side(style="thin", color="A6A6A6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def conf_fill(conf):
    if conf < MEDIUM:
        return FILL_LOW
    if conf < GOOD:
        return FILL_MEDIUM
    return None


def conf_label(conf):
    if conf < MEDIUM:
        return "faible - à vérifier"
    if conf < GOOD:
        return "moyenne"
    return "bonne"


def to_dict(result):
    return {
        "source": result.source,
        "seconds": round(result.seconds, 1),
        "fields": result.fields,
        "table": {
            "headers": result.headers,
            "rows": [
                [{"text": c.text, "conf": round(c.conf, 3), "note": c.note, "raw": c.raw} for c in cells]
                for cells in result.rows
            ],
        },
        "raw_lines": [{"text": t, "conf": round(c, 3)} for t, c in result.raw_lines],
    }


def write_json(result, path):
    Path(path).write_text(json.dumps(to_dict(result), ensure_ascii=False, indent=2), encoding="utf-8")


# Adresse de l'API qui reçoit les résultats (ex. http://serveur/api/formulaires). Vide : pas d'envoi.
API_URL = os.environ.get("OCR_API_URL", "")


def send_json(data, url=None, timeout=30):
    """Envoie le résultat (dict de to_dict) à l'API en JSON (POST).
    Retourne (code HTTP, réponse de l'API : dict si elle répond en JSON, sinon texte).
    Seul ce texte part : l'image du formulaire et le modèle restent sur l'ordinateur.
    Lève une erreur (URLError / HTTPError) si l'API ne répond pas ou refuse."""
    url = url or API_URL
    if not url:
        raise ValueError("aucune adresse d'API (option --api ou variable OCR_API_URL)")
    request = urllib.request.Request(url, data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        try:
            return response.status, json.loads(body)
        except ValueError:
            return response.status, body


def _xl_image(pil_image, max_width=260, max_height=70):
    image = pil_image.convert("RGB")
    image.thumbnail((max_width, max_height))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    xl = XLImage(buffer)
    return xl, image.height


def _style_header(sheet):
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = FILL_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    sheet.freeze_panes = "A2"


def write_excel(result, path):
    wb = Workbook()

    # 1) Champs du haut du formulaire
    ws = wb.active
    ws.title = "Champs"
    ws.sheet_view.rightToLeft = True
    ws.append(["Champ", "Valeur lue", "Confiance", "Remarque", "Ligne brute lue par le modèle"])
    for f in result.fields:
        ws.append([f["label"], f["value"], round(f["conf"], 2), f["note"] or conf_label(f["conf"]), f["raw"]])
        fill = conf_fill(f["conf"])
        if fill:
            for cell in ws[ws.max_row][:3]:
                cell.fill = fill
    for col, width in zip("ABCDE", (30, 45, 11, 40, 60)):
        ws.column_dimensions[col].width = width
    _style_header(ws)

    # 2) Tableau tel qu'il apparaît sur le formulaire
    wt = wb.create_sheet("Tableau")
    wt.sheet_view.rightToLeft = True
    # Ordre de lecture arabe : la colonne N° (à droite sur le papier) en premier
    order = list(range(len(result.headers)))
    if result.headers and result.headers[-1] == "N°":
        order.reverse()
    wt.append([result.headers[c] for c in order])
    for cells in result.rows:
        wt.append([cells[c].text for c in order])
        for out_col, c in enumerate(order, start=1):
            src = cells[c]
            target = wt.cell(row=wt.max_row, column=out_col)
            target.border = BORDER
            target.alignment = Alignment(vertical="top", wrap_text=True)
            if src.text and src.text != "" and result.headers[c] != "N°":
                fill = conf_fill(src.conf)
                if fill:
                    target.fill = fill
    for out_col in range(1, len(order) + 1):
        wt.column_dimensions[get_column_letter(out_col)].width = 8 if result.headers[order[out_col - 1]] == "N°" else 24
    _style_header(wt)
    wt.append([])
    wt.append(["Légende : orange = confiance faible (à vérifier), jaune = moyenne. "
               f"« 〃 » = même valeur que la ligne du dessus, « ↓ » = flèche (idem)."])

    # 3) Vérification : image de chaque cellule à côté du texte lu
    wv = wb.create_sheet("Vérification cellules")
    wv.sheet_view.rightToLeft = True
    wv.append(["Ligne", "Colonne", "Image de la cellule", "Texte retenu", "Lu par le modèle", "Confiance", "Remarque"])
    for cells in result.rows:
        for cell in cells:
            if not cell.text or result.headers[cell.col] == "N°" or cell.image is None:
                continue
            wv.append([cell.row, result.headers[cell.col], "", cell.text, cell.raw, round(cell.conf, 2),
                       cell.note or conf_label(cell.conf)])
            row = wv.max_row
            xl, height = _xl_image(cell.image)
            wv.add_image(xl, f"C{row}")
            wv.row_dimensions[row].height = max(20, height * 0.78)
            fill = conf_fill(cell.conf)
            if fill:
                for c in ("D", "F"):
                    wv[f"{c}{row}"].fill = fill
            for c in "ABDEFG":
                wv[f"{c}{row}"].alignment = Alignment(vertical="center", wrap_text=True)
    for col, width in zip("ABCDEFG", (7, 22, 38, 26, 26, 11, 45)):
        wv.column_dimensions[col].width = width
    _style_header(wv)

    # 4) Bandes de la partie haute (image + lignes lues)
    wb_ = wb.create_sheet("Vérification haut")
    wb_.append(["Bande", "Image"])
    for index, (box, image) in enumerate(result.strips, start=1):
        wb_.append([f"Bande {index} (y={box[1]}-{box[3]})", ""])
        xl, height = _xl_image(image, max_width=900, max_height=220)
        wb_.add_image(xl, f"B{wb_.max_row}")
        wb_.row_dimensions[wb_.max_row].height = height * 0.78
    wb_.column_dimensions["A"].width = 22
    wb_.column_dimensions["B"].width = 130
    _style_header(wb_)

    # 5) Texte brut
    wr = wb.create_sheet("Texte brut")
    wr.sheet_view.rightToLeft = True
    wr.append(["N°", "Ligne lue", "Confiance"])
    for index, (text, conf) in enumerate(result.raw_lines, start=1):
        wr.append([index, text, round(conf, 2)])
    wr.column_dimensions["B"].width = 100
    _style_header(wr)

    wb.save(path)


# ---------------------------------------------------------------- PDF
def _shape(text):
    text = str(text)
    if re.search(r"[\u0600-\u06ff]", text):
        return get_display(arabic_reshaper.reshape(text))
    return text


def _fonts():
    regular, bold = "Helvetica", "Helvetica-Bold"
    font_dir = Path("C:/Windows/Fonts")
    if (font_dir / "arial.ttf").exists():
        pdfmetrics.registerFont(TTFont("ArialU", str(font_dir / "arial.ttf")))
        regular = bold = "ArialU"
        if (font_dir / "arialbd.ttf").exists():
            pdfmetrics.registerFont(TTFont("ArialU-Bold", str(font_dir / "arialbd.ttf")))
            bold = "ArialU-Bold"
    return regular, bold


def write_pdf(result, path):
    regular, bold = _fonts()
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontName=bold, fontSize=16)
    h2 = ParagraphStyle("h", parent=styles["Heading2"], fontName=bold, fontSize=12)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontName=regular, fontSize=9, leading=12)
    rtl = ParagraphStyle("r", parent=body, alignment=TA_RIGHT)
    head = ParagraphStyle("hd", parent=body, fontName=bold)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9, textColor=colors.HexColor("#555555"))

    def p(text, header=False):
        text = str(text or "")
        style = head if header else (rtl if re.search(r"[\u0600-\u06ff]", text) else body)
        return Paragraph(escape(_shape(text)), style)

    def color_for(conf):
        if conf < MEDIUM:
            return colors.HexColor("#F8CBAD")
        if conf < GOOD:
            return colors.HexColor("#FFF2CC")
        return None

    base_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A6A6A6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    story = [
        Paragraph("Données extraites du formulaire", title),
        Paragraph(escape(f"Source : {Path(result.source).name} — lecture locale (Nanonets-OCR2-3B) en "
                         f"{result.seconds:.0f} s"), body),
        Paragraph("Orange = confiance faible, à vérifier. Jaune = confiance moyenne.", small),
        Spacer(1, 4 * mm),
        Paragraph("Champs", h2),
    ]
    data = [[p("Champ", True), p("Valeur", True), p("Confiance", True), p("Remarque", True)]]
    style = list(base_style)
    for index, f in enumerate(result.fields, start=1):
        data.append([p(f["label"]), p(f["value"]), p(f"{f['conf']:.2f}"), Paragraph(escape(_shape(f["note"])), small)])
        c = color_for(f["conf"])
        if c:
            style.append(("BACKGROUND", (0, index), (2, index), c))
    t = LongTable(data, colWidths=[55 * mm, 80 * mm, 18 * mm, 105 * mm], repeatRows=1)
    t.setStyle(TableStyle(style))
    story += [t, PageBreak()]

    if result.rows:
        story.append(Paragraph("Tableau", h2))
        order = list(range(len(result.headers)))
        if result.headers and result.headers[-1] == "N°":
            order.reverse()
        data = [[p(result.headers[c], True) for c in order]]
        style = list(base_style)
        for r_index, cells in enumerate(result.rows, start=1):
            data.append([p(cells[c].text) for c in order])
            for out_col, c in enumerate(order):
                if cells[c].text and result.headers[c] != "N°":
                    col = color_for(cells[c].conf)
                    if col:
                        style.append(("BACKGROUND", (out_col, r_index), (out_col, r_index), col))
        usable = landscape(A4)[0] - 24 * mm
        widths = [12 * mm if result.headers[c] == "N°" else (usable - 12 * mm) / (len(order) - 1) for c in order]
        t = LongTable(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle(style))
        story += [t, Spacer(1, 3 * mm)]
        notes = [(cells[c].row, result.headers[c], cells[c].note) for cells in result.rows
                 for c in range(len(cells)) if cells[c].note]
        if notes:
            story.append(Paragraph("Remarques sur les cellules", h2))
            for row, header, note in notes:
                story.append(Paragraph(escape(_shape(f"Ligne {row}, {header} : {note}")), small))

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title="Données extraites")
    doc.build(story)
