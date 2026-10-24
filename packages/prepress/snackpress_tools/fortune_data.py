"""Resolve each overlay from the same CSV row or sequence index before imposition."""

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

BARCODE_CAPTION_SIZE = 8
BARCODE_CAPTION_HEIGHT = BARCODE_CAPTION_SIZE + mm


def value_at(params, item, index):
    if item.source == "sequence":
        return params.prefix + str(params.start + index).zfill(params.digits)
    return params.csv_data.rows[index][params.csv_data.columns.index(item.column)]


def barcode_value(value, kind):
    if kind == "ean13":
        if len(value) not in (12, 13) or not value.isascii() or not value.isdigit():
            raise ValueError("EAN-13 : fournissez 12 chiffres ou 13 chiffres avec une clé valide.")
        base = value[:12]
        key = str(
            (-sum(int(digit) * (1 if i % 2 == 0 else 3) for i, digit in enumerate(base))) % 10
        )
        if len(value) == 13 and value[-1] != key:
            raise ValueError("EAN-13 : la clé de contrôle est incorrecte.")
        return base + key
    if not value or not value.isascii() or any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
        raise ValueError("Code 128 : caractères ASCII imprimables uniquement, valeur non vide.")
    return value


def barcode_drawing(item, value):
    value = barcode_value(value, item.rendering)
    drawing = createBarcodeDrawing(
        "EAN13" if item.rendering == "ean13" else "Code128",
        value=value[:12] if item.rendering == "ean13" else value,
        barWidth=1,
        barHeight=1,
        quiet=False,
        humanReadable=False,
        barFillColor=colors.HexColor(item.color),
    )
    # Ten blank modules on both sides are part of the aligned symbol width.
    module = item.barcode_width * mm / (drawing.width + 20)
    if module / mm < 0.18:
        raise ValueError("Code-barres trop dense : augmentez sa largeur ou réduisez son contenu.")
    return drawing, module


def validate_repiquages(params):
    for position, item in enumerate(params.repiquages or [], 1):
        if item.rendering == "text":
            continue
        for index in range(params.count):
            try:
                barcode_drawing(item, value_at(params, item, index))
            except ValueError as error:
                raise ValueError(f"Repiquage {position}, billet {index + 1} : {error}") from error


def draw_repiquage(canvas, item, value):
    if item.rendering == "text":
        canvas.setFont(item.font, item.size)
        draw = {
            "left": canvas.drawString,
            "center": canvas.drawCentredString,
            "right": canvas.drawRightString,
        }[item.align]
        for line, text in enumerate(value.split("\n")):
            draw(0, -line * item.size * 1.2, text.rstrip("\r"))
        return
    drawing, module = barcode_drawing(item, value)
    label = barcode_value(value, item.rendering)
    shift = {"left": 0, "center": -0.5, "right": -1}[item.align] * item.barcode_width * mm
    canvas.setFillColor(colors.white)
    canvas.rect(
        shift,
        0,
        item.barcode_width * mm,
        item.barcode_height * mm + BARCODE_CAPTION_HEIGHT,
        stroke=0,
        fill=1,
    )
    # Draw the caption separately so scaling the bars never distorts the text.
    text_width = stringWidth(label, "Helvetica", BARCODE_CAPTION_SIZE)
    font_size = BARCODE_CAPTION_SIZE * min(1, (item.barcode_width - 2) * mm / text_width)
    canvas.setFillColor(colors.HexColor(item.color))
    canvas.setFont("Helvetica", font_size)
    canvas.drawCentredString(shift + item.barcode_width * mm / 2, BARCODE_CAPTION_SIZE / 4, label)
    canvas.translate(shift + 10 * module, BARCODE_CAPTION_HEIGHT)
    canvas.scale(module, item.barcode_height * mm)
    renderPDF.draw(drawing, canvas, 0, 0)
