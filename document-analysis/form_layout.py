"""Mise en page du formulaire : redressement de la page, détection du tableau,
découpage en cellules et en lignes de texte. Aucun modèle, uniquement OpenCV."""
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

TARGET_WIDTH = 1600


@dataclass
class Table:
    box: tuple  # (x0, y0, x1, y1) dans l'image redressée
    row_lines: list  # positions y des lignes horizontales
    col_lines: list  # positions x des lignes verticales
    cells: dict = field(default_factory=dict)  # (row, col) -> (x0, y0, x1, y1)

    @property
    def n_rows(self):
        return len(self.row_lines) - 1

    @property
    def n_cols(self):
        return len(self.col_lines) - 1


def load_image(source):
    """Image RGB sur fond blanc, depuis un chemin, un fichier ouvert ou une image PIL."""
    if isinstance(source, Image.Image):
        return _on_white(source)
    with Image.open(source) as im:
        return _on_white(ImageOps.exif_transpose(im))


def _on_white(im):
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        background = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(background, im)
    return im.convert("RGB")


def _order_corners(pts):
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], np.float32)


def straighten_page(image):
    """Détecte la feuille (photo prise au téléphone) et corrige la perspective.
    Si aucune feuille nette n'est trouvée, l'image est seulement redimensionnée."""
    rgb = np.array(image)
    h, w = rgb.shape[:2]
    scale = 800 / max(h, w)
    small = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    _, bright = cv2.threshold(cv2.GaussianBlur(gray, (7, 7), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    warped = None
    if contours:
        page = max(contours, key=cv2.contourArea)
        area_ratio = cv2.contourArea(page) / (small.shape[0] * small.shape[1])
        approx = cv2.approxPolyDP(page, 0.02 * cv2.arcLength(page, True), True)
        if len(approx) != 4:
            approx = cv2.boxPoints(cv2.minAreaRect(page)).astype(np.float32)
        # On ne redresse que si la feuille occupe une grande partie mais pas tout le cadre
        if 0.35 < area_ratio < 0.97:
            corners = _order_corners(np.asarray(approx, np.float32)) / scale
            tl, tr, br, bl = corners
            width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
            height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
            dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
            matrix = cv2.getPerspectiveTransform(corners, dst)
            warped = cv2.warpPerspective(rgb, matrix, (width, height), flags=cv2.INTER_CUBIC,
                                         borderMode=cv2.BORDER_REPLICATE)
    if warped is None:
        warped = rgb
    factor = TARGET_WIDTH / warped.shape[1]
    warped = cv2.resize(warped, None, fx=factor, fy=factor,
                        interpolation=cv2.INTER_CUBIC if factor > 1 else cv2.INTER_AREA)
    return Image.fromarray(warped)


def binarize(gray):
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)


def _line_masks(binary):
    h, w = binary.shape
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (w // 18, 1)))
    vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 40)))
    horiz = cv2.dilate(horiz, np.ones((3, 3), np.uint8))
    vert = cv2.dilate(vert, np.ones((3, 3), np.uint8))
    return horiz, vert


def _cluster(positions, min_gap):
    groups = []
    for p in sorted(positions):
        if groups and p - groups[-1][-1] <= min_gap:
            groups[-1].append(p)
        else:
            groups.append([p])
    return [int(np.mean(g)) for g in groups]


def deskew(image):
    """Corrige la rotation légère de la page à partir des lignes horizontales imprimées."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    horiz, _ = _line_masks(binarize(gray))
    lines = cv2.HoughLinesP(horiz, 1, np.pi / 720, threshold=200,
                            minLineLength=image.width // 4, maxLineGap=20)
    if lines is None:
        return image
    angles = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in lines[:, 0]]
    angles = [a for a in angles if abs(a) < 8]
    if not angles:
        return image
    angle = float(np.median(angles))
    if abs(angle) < 0.15:
        return image
    return image.rotate(angle, resample=Image.BICUBIC, fillcolor=(255, 255, 255))


def detect_table(image):
    """Retourne le plus grand tableau quadrillé de la page, ou None.
    Chaque cellule est trouvée comme une zone blanche fermée par les traits du
    quadrillage, ce qui tolère une perspective ou une inclinaison résiduelle."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    binary = binarize(gray)
    horiz, vert = _line_masks(binary)
    grid = cv2.bitwise_or(horiz, vert)
    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    x, y, w, h = cv2.boundingRect(max(contours, key=lambda c: cv2.boundingRect(c)[2] * cv2.boundingRect(c)[3]))
    if w < image.width * 0.4 or h < image.height * 0.1:
        return None

    roi = grid[y:y + h, x:x + w].copy()
    # Ferme le cadre extérieur s'il est incomplet
    cv2.rectangle(roi, (0, 0), (w - 1, h - 1), 255, 3)
    # Prolonge les traits pour boucher les petites coupures
    roi = cv2.morphologyEx(roi, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1)))
    roi = cv2.morphologyEx(roi, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(roi), connectivity=4)
    boxes = []
    for i in range(1, count):
        cx, cy, cw, ch, area = stats[i]
        if cw < 25 or ch < 25 or area < 0.6 * cw * ch:
            continue
        if cw > 0.95 * w and ch > 0.5 * h:
            continue
        boxes.append((x + cx, y + cy, x + cx + cw, y + cy + ch))
    if len(boxes) < 4:
        return None

    # Regroupe les cellules en lignes (centres verticaux proches)
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    rows = []
    for b in boxes:
        cy = (b[1] + b[3]) / 2
        if rows and abs(cy - rows[-1]["cy"]) < 0.45 * (b[3] - b[1]):
            rows[-1]["boxes"].append(b)
            rows[-1]["cy"] = np.mean([(c[1] + c[3]) / 2 for c in rows[-1]["boxes"]])
        else:
            rows.append({"cy": cy, "boxes": [b]})

    # Les colonnes sont définies par la ligne qui compte le plus de cellules
    # (nombre le plus fréquent : les flèches dessinées à la main coupent parfois une cellule)
    counts = [len(r["boxes"]) for r in rows]
    usual = max(set(counts), key=lambda n: (counts.count(n), n))
    widest = [r for r in rows if len(r["boxes"]) == usual][-1]
    col_spans = sorted((b[0], b[2]) for b in widest["boxes"])
    table = Table(box=(x, y, x + w, y + h),
                  row_lines=[int(min(b[1] for b in r["boxes"])) for r in rows] + [y + h],
                  col_lines=[s[0] for s in col_spans] + [col_spans[-1][1]])
    table.row_boxes = []
    for r_index, row in enumerate(rows):
        table.row_boxes.append(row["boxes"])
        for b in row["boxes"]:
            # Colonne = celle de la ligne de référence qui recouvre le plus la cellule
            overlaps = [max(0, min(b[2], e) - max(b[0], s)) for s, e in col_spans]
            c_index = int(np.argmax(overlaps))
            if (r_index, c_index) in table.cells:
                old = table.cells[(r_index, c_index)]
                b = (min(old[0], b[0]), min(old[1], b[1]), max(old[2], b[2]), max(old[3], b[3]))
            table.cells[(r_index, c_index)] = b
    return table


def find_boxes(image, bottom):
    """Cases encadrées de la partie haute (numéro écrit dans un rectangle, libellé imprimé
    dessous : « الرقم الموحد », « رقم الانخراط »…). Zones blanches fermées par des traits,
    plus larges que hautes, triées de haut en bas."""
    gray = cv2.cvtColor(np.array(image.crop((0, 0, image.width, bottom))), cv2.COLOR_RGB2GRAY)
    binary = binarize(gray)
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (60, 1)))
    vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30)))
    frame = cv2.dilate(cv2.bitwise_or(horiz, vert), np.ones((5, 5), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(frame), connectivity=4)
    boxes = []
    for i in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[i])
        if 40 <= h <= 200 and 150 <= w <= 0.6 * image.width and w > 1.5 * h and area > 0.6 * w * h:
            boxes.append((x, y, x + w, y + h))
    return sorted(boxes, key=lambda b: b[1])


def _box_ink(image, box):
    return binarize(cv2.cvtColor(np.array(image.crop(box)), cv2.COLOR_RGB2GRAY))


def crossed_out(image, box):
    """Case barrée d'une croix : un seul trait d'encre couvre presque toute la case
    (des chiffres sont des taches séparées, chacune bien plus petite que la case)."""
    binary = _box_ink(image, box)
    h, w = binary.shape
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    return any(stats[i][2] > 0.8 * w and stats[i][3] > 0.8 * h for i in range(1, count))


def middle_gap(image, box):
    """Abscisse de la colonne la moins encrée près du milieu de la case : on coupe entre deux
    chiffres (les traits horizontaux, ex. une ellipse qui traverse la case, sont ignorés)."""
    binary = cv2.morphologyEx(_box_ink(image, box), cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9)))
    profile = np.convolve((binary > 0).sum(axis=0).astype(float), np.ones(5) / 5, mode="same")
    w = box[2] - box[0]
    lo, hi = int(0.38 * w), int(0.62 * w)
    return box[0] + lo + int(np.argmin(profile[lo:hi]))


def ink_ratio(image, box, margin=6):
    """Proportion de pixels d'encre dans une zone, sans les bords de la cellule."""
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 + margin, y0 + margin, x1 - margin, y1 - margin
    if x1 <= x0 or y1 <= y0:
        return 0.0
    gray = cv2.cvtColor(np.array(image.crop((x0, y0, x1, y1))), cv2.COLOR_RGB2GRAY)
    binary = binarize(gray)
    h, w = binary.shape
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, int(0.7 * w)), 1)))
    vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, int(0.8 * h)))))
    binary = cv2.subtract(binary, cv2.dilate(cv2.bitwise_or(horiz, vert), np.ones((3, 3), np.uint8)))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return float((binary > 0).mean())


def debug_draw(image, table, bands, path):
    canvas = np.array(image).copy()
    if table:
        for (r, c), (x0, y0, x1, y1) in table.cells.items():
            cv2.rectangle(canvas, (x0, y0), (x1, y1), (255, 0, 0), 2)
    for top, bottom in bands:
        cv2.rectangle(canvas, (4, top), (image.width - 4, bottom), (0, 160, 0), 2)
    Image.fromarray(canvas).save(path)
