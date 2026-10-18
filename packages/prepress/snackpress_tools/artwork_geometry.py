"""Validate finished dimensions and the real bleed available around them."""

import pikepdf
from reportlab.lib.units import mm


def validate_page(page, width, height, bleed, label):
    if int(page.obj.get("/Rotate", 0)) % 360 or float(page.obj.get("/UserUnit", 1)) != 1:
        raise ValueError("Normalisez la rotation et les unités des fichiers du BAT.")
    media = [float(n) / mm for n in page.mediabox]
    trim = [float(n) / mm for n in page.trimbox]
    expected_width, expected_height = width + 2 * bleed, height + 2 * bleed
    # A PDF without a useful TrimBox can still declare the complete file format.
    if all(abs(a - b) < 0.01 for a, b in zip(trim, media, strict=True)) and (
        abs(media[2] - media[0] - expected_width) <= 0.1
        and abs(media[3] - media[1] - expected_height) <= 0.1
    ):
        trim = [media[0] + bleed, media[1] + bleed, media[2] - bleed, media[3] - bleed]
    x0, y0, x1, y1 = trim
    if abs(x1 - x0 - width) > 0.1 or abs(y1 - y0 - height) > 0.1:
        raise ValueError(
            f"{label} : format incompatible ; format fini attendu {width:g} × {height:g} mm ; "
            f"fichier avec fond perdu attendu {expected_width:g} × {expected_height:g} mm "
            f"({bleed:g} mm sur chaque côté)."
        )
    # CropBox controls viewing, not the physical amount of artwork in the file.
    bleedbox = page.obj.get("/BleedBox", page.mediabox)
    bx0, by0, bx1, by1 = [float(n) / mm for n in bleedbox]
    mx0, my0, mx1, my1 = media
    if (
        min(x0 - mx0, y0 - my0, mx1 - x1, my1 - y1) < -0.1
        or min(bx0 - mx0, by0 - my0, mx1 - bx1, my1 - by1) < -0.1
        or bx1 <= bx0
        or by1 <= by0
    ):
        raise ValueError("Les zones de coupe et de fond perdu doivent rester dans la page.")
    if min(x0 - bx0, y0 - by0, bx1 - x1, by1 - y1) + 0.1 < bleed:
        raise ValueError(
            f"{label} : fond perdu de {bleed:g} mm attendu sur chaque côté ; "
            f"fichier attendu {expected_width:g} × {expected_height:g} mm "
            f"pour un format fini de {width:g} × {height:g} mm."
        )
    page.TrimBox = pikepdf.Array([n * mm for n in trim])
    page.BleedBox = pikepdf.Array(bleedbox)
    return pikepdf.Array(
        [(x0 - bleed) * mm, (y0 - bleed) * mm, (x1 + bleed) * mm, (y1 + bleed) * mm]
    )
