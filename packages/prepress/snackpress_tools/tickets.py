"""Vector variable data, repeated serials, optional codes and booklet manifest."""

from contextlib import ExitStack
from math import ceil

import pikepdf
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128, qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from .common import INK, new_canvas, open_pdf, report


def serial(settings, index, offset=0):
    return (
        settings.prefix
        + str(settings.start + index + offset).zfill(settings.digits)
        + settings.suffix
    )


def generate_series(folder, component, files, preview=False):
    settings = component.tickets
    indices = list(dict.fromkeys([0, settings.count - 1])) if preview else range(settings.count)
    overlay = folder / "numerotation.pdf"
    c = new_canvas(overlay, component.width, component.height)
    for index in indices:
        for face in range(1, len(files) + 1):
            c.setFillColor(INK)
            for placement in settings.placements:
                if placement.face != face:
                    continue
                value = serial(settings, index, placement.offset)
                text_width = stringWidth(value, "SnackBold", placement.size) / mm
                if placement.x + text_width > component.width or placement.y < placement.size / mm:
                    raise ValueError(
                        "La numérotation dépasse du billet. Déplacez-la ou réduisez sa taille."
                    )
                c.setFont("SnackBold", placement.size)
                c.drawString(placement.x * mm, (component.height - placement.y) * mm, value)
            if face == 1 and settings.code != "none":
                payload = settings.payload.replace("{n}", serial(settings, index))
                x, y = settings.code_x * mm, (component.height - settings.code_y - 22) * mm
                if settings.code == "qr":
                    widget = qr.QrCodeWidget(payload, barLevel="M", barBorder=4)
                    bounds = widget.getBounds()
                    widget.qr.make()
                    if 22 / (widget.qr.getModuleCount() + 8) < 0.25:
                        raise ValueError("QR trop dense : réduisez son contenu.")
                    scale = 22 * mm / (bounds[2] - bounds[0])
                    drawing = Drawing(22 * mm, 22 * mm, transform=[scale, 0, 0, scale, 0, 0])
                    drawing.add(widget)
                    renderPDF.draw(drawing, c, x, y)
                else:
                    if not payload.isascii() or any(ord(ch) < 32 for ch in payload):
                        raise ValueError("Code 128 : caractères ASCII imprimables uniquement.")
                    barcode = code128.Code128(payload, barWidth=0.25 * mm, barHeight=12 * mm)
                    available = (component.width - settings.code_x) * mm
                    scale = min(1, available / barcode.width)
                    if scale * 0.25 < 0.18:
                        raise ValueError("Code 128 trop long pour le billet.")
                    c.saveState()
                    c.translate(x, y)
                    c.scale(scale, 1)
                    barcode.drawOn(c, 0, 0)
                    c.restoreState()
            c.showPage()
    c.save()
    out = pikepdf.Pdf.new()
    sources = []
    stack = ExitStack()
    try:
        for file in files:
            doc = stack.enter_context(open_pdf(file, max_pages=1))
            sources.append(doc)
            page = doc.pages[0]
            if int(page.obj.get("/Rotate", 0)) % 360 or float(page.obj.get("/UserUnit", 1)) != 1:
                raise ValueError("Normalisez la rotation et les unités du billet.")
            box = [float(n) for n in page.trimbox]
            if (
                abs((box[2] - box[0]) / mm - component.width) > 0.02
                or abs((box[3] - box[1]) / mm - component.height) > 0.02
            ):
                raise ValueError("Le format fini du billet doit correspondre à sa TrimBox.")
        with pikepdf.open(overlay) as variable:
            for page_index, layer in enumerate(variable.pages):
                source = sources[page_index % len(files)].pages[0]
                media = [float(n) for n in source.mediabox]
                target = out.add_blank_page(page_size=(media[2] - media[0], media[3] - media[1]))
                target.MediaBox = pikepdf.Array(media)
                target.TrimBox = pikepdf.Array(source.trimbox)
                target.BleedBox = pikepdf.Array(source.bleedbox)
                target.CropBox = pikepdf.Array(source.cropbox)
                background = source.as_form_xobject()
                background.BBox = pikepdf.Array(media)
                target.add_overlay(background, pikepdf.Rectangle(*media))
                target.add_overlay(layer, pikepdf.Rectangle(*[float(n) for n in source.trimbox]))
            path = folder / ("echantillon-billets.pdf" if preview else "serie-billets.pdf")
            out.save(path)
    finally:
        stack.close()
        out.close()
    manifest = folder / "carnets.pdf"
    rows = [
        ("Quantité", settings.count),
        ("Premier numéro", serial(settings, 0)),
        ("Dernier numéro", serial(settings, settings.count - 1)),
        (
            "Reliure",
            {"loose": "Billets séparés", "stapled": "Agrafage", "glued": "Encollage"}[
                settings.binding
            ],
        ),
    ]
    for i, placement in enumerate(settings.placements):
        rows.append(
            (
                f"Position {i + 1}",
                f"Face {placement.face} ; {placement.x} × {placement.y} mm ; "
                f"{serial(settings, 0, placement.offset)} → "
                f"{serial(settings, settings.count - 1, placement.offset)}",
            )
        )
    if settings.binding != "loose":
        for book in range(ceil(settings.count / settings.per_book)):
            first = book * settings.per_book
            last = min(settings.count, first + settings.per_book) - 1
            rows.append(
                (
                    f"Carnet {book + 1}",
                    f"{serial(settings, first)} → {serial(settings, last)} ; "
                    f"{last - first + 1} billets",
                )
            )
    report(
        manifest,
        "Billets détachables numérotés",
        rows,
        "Coordonnées depuis le coin supérieur gauche du format fini. "
        "Série dans l’ordre des numéros, recto puis verso. "
        "Perforations et reliure à réaliser en fabrication ; tester les codes sur une épreuve.",
    )
    return path, manifest
