"""Ouverture d'un document à analyser : image (PNG, JPG, TIFF multipage...) ou PDF (toutes les pages)."""
from PIL import Image, ImageSequence, UnidentifiedImageError

from form_layout import load_image

MAX_PAGES = 10
PDF_DPI = 200  # assez fin pour l'écriture manuscrite ; redimensionné ensuite à 1600 px de large


def is_pdf(source):
    if isinstance(source, (str, bytes)) or hasattr(source, "__fspath__"):
        with open(source, "rb") as handle:
            return handle.read(5) == b"%PDF-"
    start = source.read(5)
    source.seek(0)
    return start == b"%PDF-"


def pdf_pages(source):
    try:
        import pypdfium2 as pdfium
    except ImportError as error:
        raise ValueError("Lecture des PDF indisponible : installer pypdfium2 (pip install pypdfium2)") from error
    data = source.read() if hasattr(source, "read") else open(source, "rb").read()
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        raise ValueError("PDF illisible ou protégé par un mot de passe") from error
    return [pdf[i].render(scale=PDF_DPI / 72).to_pil().convert("RGB") for i in range(min(len(pdf), MAX_PAGES))]


def load_pages(source, check_only=False):
    """Pages du document en images RGB. check_only : vérifie seulement que le fichier est lisible.
    Une image d'une seule page est ouverte exactement comme avant (form_layout.load_image)."""
    if is_pdf(source):
        if check_only:
            return []
        return pdf_pages(source)
    try:
        with Image.open(source) as image:
            frames = getattr(image, "n_frames", 1)
            if check_only:
                image.verify()
                return []
            if frames == 1:
                if hasattr(source, "seek"):
                    source.seek(0)
                return [load_image(source)]
            return [load_image(frame.copy()) for frame in ImageSequence.Iterator(image)][:MAX_PAGES]
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Format non reconnu : envoyer une image (PNG, JPG, TIFF...) ou un PDF") from error
