"""Synthetic artwork matching the current proof's template and file roles."""

import shutil

import pikepdf
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from .burger import input_labels, template
from .catalog import Burger, ToolResult
from .common import artifact, new_canvas


def artwork(path, width, height, trim, label, pages, *, finish=False):
    c = new_canvas(path, width, height)
    x, y, w, h = trim
    for index in range(pages):
        back = index % 2 == 1
        c.setFillColor(colors.HexColor("#183d36" if back or finish else "#f7e5dc"))
        c.rect(0, 0, width * mm, height * mm, fill=1, stroke=0)
        c.setFillColor(colors.white if back or finish else colors.HexColor("#183d36"))
        inset = min(w, h) * 0.1
        left, baseline = (x + inset) * mm, (y + h * 0.65) * mm
        size = min(w * mm / 9, h * mm / 5)
        c.setFont("SnackDisplay", size)
        c.drawString(left, baseline, "studio papier.")
        label_size = min(size * 0.3, (w - inset * 2) * mm / stringWidth(label, "Snack", 1))
        c.setFont("Snack", label_size)
        c.drawString(left, (y + h * 0.43) * mm, label)
        c.setFont("Snack", size * 0.3)
        c.drawString(left, (y + h * 0.32) * mm, f"Exemple — page {index + 1} / {pages}")
        c.drawString(left, (y + inset) * mm, f"Format fini : {w:g} × {h:g} mm")
        c.setFillColor(colors.HexColor("#c96d4d"))
        c.rect(left, (y + h * 0.54) * mm, w * 0.2 * mm, h * 0.015 * mm, fill=1, stroke=0)
        c.showPage()
    c.save()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for page in pdf.pages:
            page.TrimBox = pikepdf.Array([x * mm, y * mm, (x + w) * mm, (y + h) * mm])
            page.BleedBox = page.MediaBox
        pdf.save(path)


def distribute(pages, files):
    if pages < files:
        raise ValueError("Prévoyez au moins une page par fichier pour charger l’exemple.")
    return [pages // files + (index < pages % files) for index in range(files)]


def burger_example(folder, files, settings):
    p = Burger.model_validate(settings)
    if p.source_mode != "classic" or p.product_snapshot is not None:
        raise ValueError("L’exemple est disponible dans le mode classique du BAT.")
    if len(files) != int(p.template_tool == "pdf"):
        raise ValueError("Importez le gabarit PDF avant de charger un exemple à son format.")
    if p.document_type == "brochure":
        counts = distribute(4, p.cover_files) + distribute(
            p.interior_pages, p.expected_files - p.cover_files
        )
    else:
        counts = [2 if p.expected_files == 1 else 1] * p.expected_files
    counts += [sum(counts)] * len(p.finishes)
    if sum(counts) > 200:
        raise ValueError("L’exemple dépasse les 200 pages source autorisées pour le BAT.")
    guide = template(folder, files, p)
    if guide:
        _, (width, height), trim = guide
        if p.template_tool == "sushi":
            bleed = p.template_settings["bleed"]
            _, _, width, height = trim
            trim = (bleed, bleed, width, height)
            width, height = width + 2 * bleed, height + 2 * bleed
        elif p.template_tool == "taco":
            # The guide's technical margins are not part of the artwork format.
            _, _, width, height = trim
            trim = (0, 0, width, height)
    elif p.document_type == "brochure":
        width, height, trim = 148, 210, (0, 0, 148, 210)
    else:
        width, height, trim = 91, 61, (3, 3, 85, 55)
    artifacts = []
    for index, (label, pages) in enumerate(zip(input_labels(p), counts, strict=True)):
        path = folder / f"exemple-{index + 1}.pdf"
        artwork(path, width, height, trim, label, pages, finish=index >= p.expected_files)
        artifacts.append(artifact(path, label))
    if p.template_tool == "pdf":
        path = folder / "exemple-gabarit.pdf"
        shutil.copyfile(files[0], path)
        artifacts.append(artifact(path, "Gabarit PDF"))
    return ToolResult(tool="burger", summary="Exemple adapté au gabarit.", artifacts=artifacts)
