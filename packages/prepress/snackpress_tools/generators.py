from math import ceil

import pikepdf
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128, qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.colors import CMYKColorSep
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .catalog import ToolResult
from .common import CORAL, INK, artifact, new_canvas, open_pdf, render_page, report


def burger(folder, files, p):
    with open_pdf(files[0], max_pages=2) as doc:
        count = len(doc.pages)
    path = folder / "bat.pdf"
    c = new_canvas(path, 210, 297)
    specs = [("Projet", p.title), ("Client", p.client or "Non renseigné"), ("Papier", p.paper)]
    for index in range(count):
        img, (w, h) = render_page(files[0], index, dpi=120)
        c.setFillColor(INK)
        c.setFont("SnackBold", 18)
        c.drawString(18 * mm, 272 * mm, p.title)
        c.setFont("Snack", 10)
        face = "Recto" if index == 0 else "Verso"
        c.drawString(18 * mm, 260 * mm, f"{face} — {w:.2f} × {h:.2f} mm")
        scale = min(174 / w, 190 / h)
        dw, dh = w * scale, h * scale
        c.drawImage(
            ImageReader(img),
            (210 - dw) / 2 * mm,
            (65 + (190 - dh) / 2) * mm,
            width=dw * mm,
            height=dh * mm,
        )
        c.setFont("Snack", 8)
        c.drawString(18 * mm, 38 * mm, "BAT DE PRÉSENTATION — COULEURS NON CONTRACTUELLES")
        c.drawString(
            18 * mm,
            31 * mm,
            "Aperçu ajusté à la page A4. Ne pas utiliser comme fichier d’impression.",
        )
        c.drawString(18 * mm, 22 * mm, f"Client : {p.client[:75] or 'Non renseigné'}")
        c.showPage()
        specs.append((face, f"Zone visible {w:.2f} × {h:.2f} mm ; aperçu à {scale * 100:.1f} %"))
    c.save()
    sheet = folder / "fiche-technique.pdf"
    report(
        sheet,
        "Fiche technique du BAT",
        specs + [("Commentaires", p.notes or "Aucun")],
        (
            "Présentation rasterisée. Couleurs non contractuelles. Validation "
            "du BAT à organiser séparément."
        ),
    )
    return ToolResult(
        tool="burger",
        summary=f"BAT A4 de {count} face(s) et fiche technique prêts.",
        metrics={"Faces": count},
        artifacts=[artifact(path, "BAT A4"), artifact(sheet, "Fiche technique")],
    )


def pizza(folder, files, p):
    path = folder / "gabarit.pdf"
    w, h = p.width + 2 * p.bleed, p.height + 2 * p.bleed
    c = new_canvas(path, w, h)
    c.setFillColor(colors.HexColor("#f7e5dc"))
    c.rect(0, 0, w * mm, h * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.rect(p.bleed * mm, p.bleed * mm, p.width * mm, p.height * mm, fill=1, stroke=0)
    c.setStrokeColor(CORAL)
    c.setLineWidth(0.25 * mm)
    c.rect(p.bleed * mm, p.bleed * mm, p.width * mm, p.height * mm)
    c.setStrokeColor(INK)
    c.setDash(2 * mm, 1 * mm)
    c.rect(
        (p.bleed + p.safety) * mm,
        (p.bleed + p.safety) * mm,
        (p.width - 2 * p.safety) * mm,
        (p.height - 2 * p.safety) * mm,
    )
    c.save()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        page.TrimBox = pikepdf.Array(
            [p.bleed * mm, p.bleed * mm, (p.bleed + p.width) * mm, (p.bleed + p.height) * mm]
        )
        page.BleedBox = page.MediaBox
        pdf.save(path)
    sheet = folder / "legende.pdf"
    report(
        sheet,
        "Pizza — gabarit technique",
        [
            ("Format fini", f"{p.width} × {p.height} mm"),
            ("Fond perdu", f"{p.bleed} mm, zone saumon"),
            ("Sécurité", f"{p.safety} mm, trait vert pointillé"),
            ("Coupe", "Trait corail continu ; TrimBox définie"),
        ],
        "Guides visibles : gabarit de préparation, à retirer du document final.",
    )
    return ToolResult(
        tool="pizza",
        summary="Gabarit à taille réelle avec TrimBox et BleedBox.",
        metrics={"Largeur finie (mm)": p.width, "Hauteur finie (mm)": p.height},
        artifacts=[artifact(path, "Gabarit PDF 1:1"), artifact(sheet, "Légende des guides")],
    )


def fold_widths(p):
    if p.fold == "gate":
        widths = [
            p.width / 4 - p.allowance / 2,
            p.width / 4 + p.allowance / 2,
            p.width / 4 + p.allowance / 2,
            p.width / 4 - p.allowance / 2,
        ]
    elif p.fold == "roll":
        # Each successively nested panel loses the same allowance.
        outer = (p.width + p.allowance * p.panels * (p.panels - 1) / 2) / p.panels
        widths = [outer - i * p.allowance for i in range(p.panels)]
    else:
        widths = [p.width / p.panels] * p.panels
    if min(widths) <= 5:
        raise ValueError("Un panneau est trop petit. Réduisez le retrait ou le nombre de panneaux.")
    return widths


def taco(folder, files, p):
    widths = fold_widths(p)
    path = folder / "plan-pliage.pdf"
    border = 15
    c = new_canvas(path, p.width + border * 2, p.height + border * 2)
    x = border
    for i, width in enumerate(widths):
        c.setFillColor(colors.HexColor("#eef1e7") if i % 2 == 0 else colors.white)
        c.setStrokeColor(INK)
        c.rect(x * mm, border * mm, width * mm, p.height * mm, fill=1)
        c.setFillColor(INK)
        c.setFont("Snack", max(5, min(12, width * mm / 12)))
        c.drawCentredString((x + width / 2) * mm, (border + p.height / 2) * mm, f"Panneau {i + 1}")
        c.drawCentredString(
            (x + width / 2) * mm, (border + p.height / 2 - 6) * mm, f"{width:.2f} mm"
        )
        x += width
        if i < len(widths) - 1:
            c.setStrokeColor(CORAL)
            c.setDash(3 * mm, 2 * mm)
            c.line(x * mm, border * mm, x * mm, (border + p.height) * mm)
            c.setDash()
    c.setFont("Snack", 8)
    c.drawString(
        border * mm, 6 * mm, "Vue à plat — plis corail — contrôler l’ordre des faces au façonnage"
    )
    c.save()
    sheet = folder / "fiche-pliage.pdf"
    report(
        sheet,
        "Taco — plan de panneaux",
        [
            ("Type", p.fold),
            ("À plat", f"{p.width} × {p.height} mm"),
            *[(f"Panneau {i + 1} (gauche à droite)", f"{w:.3f} mm") for i, w in enumerate(widths)],
        ],
        (
            "Schéma indicatif, sans simulation de pliage. Valider dimensions, "
            "retraits et faces avec le façonnier."
        ),
    )
    return ToolResult(
        tool="taco",
        summary=f"Plan à plat de {len(widths)} panneaux.",
        metrics={"Panneaux": len(widths), "Largeur totale (mm)": round(sum(widths), 3)},
        artifacts=[artifact(path, "Plan de pliage 1:1"), artifact(sheet, "Fiche des panneaux")],
    )


def eyelets(p):
    x0, x1, y0, y1 = p.inset, p.width - p.inset, p.inset, p.height - p.inset
    nx, ny = max(1, ceil((x1 - x0) / p.spacing)), max(1, ceil((y1 - y0) / p.spacing))
    points = {(round(x0 + (x1 - x0) * i / nx, 5), y) for i in range(nx + 1) for y in (y0, y1)}
    points |= {(x, round(y0 + (y1 - y0) * i / ny, 5)) for i in range(ny + 1) for x in (x0, x1)}
    return sorted({(round(x, 5), round(y, 5)) for x, y in points})


def burrito(folder, files, p):
    points = eyelets(p)
    path = folder / "plan-bache.pdf"
    # The finished format is unchanged; the upper sleeve is shown outside it.
    c = new_canvas(path, p.width, p.height + p.sleeve)
    c.setStrokeColor(INK)
    c.setLineWidth(0.4 * mm)
    c.rect(0, 0, p.width * mm, p.height * mm)
    c.setStrokeColor(CORAL)
    c.setDash(5 * mm, 3 * mm)
    c.rect(p.hem * mm, p.hem * mm, (p.width - 2 * p.hem) * mm, (p.height - 2 * p.hem) * mm)
    if p.sleeve:
        c.rect(0, p.height * mm, p.width * mm, p.sleeve * mm)
    c.setDash()
    c.setStrokeColor(INK)
    for x, y in points:
        c.circle(x * mm, y * mm, 4 * mm)
        c.line((x - 6) * mm, y * mm, (x + 6) * mm, y * mm)
        c.line(x * mm, (y - 6) * mm, x * mm, (y + 6) * mm)
    c.setFillColor(INK)
    c.setFont("Snack", max(8, min(60, p.width / 30)))
    c.drawCentredString(
        p.width / 2 * mm, p.height / 2 * mm, f"FORMAT FINI {p.width:g} × {p.height:g} mm"
    )
    c.save()
    sheet = folder / "fiche-bache.pdf"
    report(
        sheet,
        "Burrito — plan technique",
        [
            ("Format fini", f"{p.width} × {p.height} mm"),
            ("Ourlet intérieur", f"{p.hem} mm sur les 4 côtés"),
            ("Fourreau", f"{p.sleeve} mm ajoutés au-dessus ; développement à confirmer"),
            ("Œillets", f"{len(points)} centres, retrait {p.inset} mm, entraxe ≤ {p.spacing} mm"),
            ("Coordonnées des centres", "; ".join(f"({x:g}, {y:g})" for x, y in points)),
        ],
        (
            "Plan uniquement : aucun visuel source modifié. Coordonnées en mm "
            "depuis le coin inférieur gauche du format fini. Valider la "
            "fabrication."
        ),
    )
    return ToolResult(
        tool="burrito",
        summary=f"Plan technique avec {len(points)} œillets.",
        metrics={"Œillets": len(points)},
        artifacts=[
            artifact(path, "Plan grand format 1:1"),
            artifact(sheet, "Fiche et coordonnées"),
        ],
    )


def club(folder, files, p):
    leaves = p.pages // 2
    microns = p.gsm * p.bulk if p.mode == "bulk" else p.caliper
    block = leaves * microns / 1000
    spine = block + p.glue
    path = folder / "estimation-dos.pdf"
    report(
        path,
        "Club Sandwich — estimation du dos",
        [
            ("Pages intérieures", p.pages),
            ("Feuilles dans le bloc", leaves),
            ("Méthode", "Grammage × main" if p.mode == "bulk" else "Calibre mesuré"),
            ("Épaisseur par feuille", f"{microns:.2f} µm"),
            ("Bloc papier", f"{block:.3f} mm"),
            ("Marge de colle", f"{p.glue:.3f} mm"),
            ("Dos estimé", f"{spine:.3f} mm"),
        ],
        (
            "Estimation pour dos carré collé, hors couverture. Compression, "
            "colle et conditions de reliure varient : confirmer au relieur."
        ),
    )
    return ToolResult(
        tool="club-sandwich",
        summary=f"Dos estimé : {spine:.2f} mm.",
        metrics={
            "Dos estimé (mm)": round(spine, 3),
            "Bloc papier (mm)": round(block, 3),
            "Feuilles": leaves,
        },
        artifacts=[artifact(path, "Estimation et formule")],
    )


def sushi(folder, files, p):
    try:
        creases = [float(x.strip()) for x in p.creases.split(",") if x.strip()]
    except ValueError as exc:
        raise ValueError("Rainages invalides : saisissez des positions en mm, ex. 25, 60.") from exc
    if len(creases) > 100 or any(not 0 < x < p.width for x in creases):
        raise ValueError("Les rainages doivent rester strictement dans la largeur du contour.")
    path = folder / "contours.pdf"
    pad = 5
    c = new_canvas(path, p.width + 2 * pad, p.height + 2 * pad)
    c.setLineWidth(0.1 * mm)
    c.setStrokeOverprint(True)
    c.setStrokeColor(CMYKColorSep(0, 100, 0, 0, spotName=p.cut_name))
    if p.shape == "circle":
        c.circle((pad + p.width / 2) * mm, (pad + p.height / 2) * mm, p.width / 2 * mm)
    else:
        c.rect(pad * mm, pad * mm, p.width * mm, p.height * mm)
    c.setStrokeColor(CMYKColorSep(100, 0, 0, 0, spotName=p.crease_name))
    for x in creases:
        c.line((pad + x) * mm, pad * mm, (pad + x) * mm, (pad + p.height) * mm)
    c.save()
    sheet = folder / "convention.pdf"
    report(
        sheet,
        "Sushi — convention de tracé",
        [
            ("Format", f"{p.width} × {p.height} mm, {p.shape}"),
            ("Découpe", p.cut_name),
            ("Rainage", p.crease_name),
            ("Rainages (mm)", p.creases or "Aucun"),
            ("Trait", "Vectoriel 0,1 mm, sans remplissage, surimpression activée"),
            ("Origine du contour", "5 mm depuis les bords de la page, marge technique"),
        ],
        (
            "Confirmer les noms de tons directs, l’épaisseur de trait et la "
            "surimpression avec l’atelier avant utilisation."
        ),
    )
    return ToolResult(
        tool="sushi",
        summary="Contours vectoriels en deux tons directs nommés.",
        metrics={"Rainages": len(creases)},
        artifacts=[
            artifact(path, "Contours PDF vectoriels"),
            artifact(sheet, "Convention atelier"),
        ],
    )


def kebab(folder, files, p):
    path = folder / "fiche-fabrication.pdf"
    report(
        path,
        p.title,
        [
            ("Client / projet", p.client or "Non renseigné"),
            ("Papier", p.paper),
            ("Quantité", p.quantity),
            ("Couleurs / faces", p.colors),
            ("Finitions", p.finishing),
            ("Consignes", p.notes or "Aucune"),
        ],
        (
            "Fiche d’instructions déclaratives : aucune validation automatique"
            " des choix de fabrication."
        ),
    )
    return ToolResult(
        tool="kebab",
        summary="Fiche d’instructions prête pour l’atelier.",
        artifacts=[artifact(path, "Fiche de fabrication")],
    )


def fortune(folder, files, p):
    path = folder / "serie.pdf"
    overlay = folder / "variable.pdf"
    c = new_canvas(overlay, p.width, p.height)
    for index in range(p.count):
        serial = p.prefix + str(p.start + index).zfill(p.digits)
        payload = p.payload.replace("{n}", serial)
        c.setFillColor(INK)
        # Reserve only the variable fields, preserving the rest of optional artwork.
        c.setFillColor(colors.white)
        c.rect(
            5 * mm,
            (p.height - 11) * mm,
            min((p.width - 10) * mm, pdf_text_width(p.text, 8) + 2 * mm),
            5 * mm,
            fill=1,
            stroke=0,
        )
        c.setFillColor(INK)
        c.setFont("Snack", 8)
        if pdf_text_width(p.text, 8) > (p.width - 12) * mm:
            raise ValueError(
                "Le texte est trop long pour ce format. Raccourcissez-le ou agrandissez la page."
            )
        c.drawString(6 * mm, (p.height - 10) * mm, p.text)
        size = min(22, p.width - 16, p.height - 27)
        if p.code == "qr":
            c.setFillColor(colors.white)
            c.rect(5 * mm, 10 * mm, (size + 2) * mm, (size + 2) * mm, fill=1, stroke=0)
            c.setFillColor(INK)
            widget = qr.QrCodeWidget(payload, barLevel="M", barBorder=4)
            bounds = widget.getBounds()
            width = bounds[2] - bounds[0]
            widget.qr.make()
            if size / (widget.qr.getModuleCount() + 8) < 0.25:
                raise ValueError(
                    "QR trop dense pour ce format. Réduisez le contenu ou agrandissez le support."
                )
            drawing = Drawing(
                size * mm, size * mm, transform=[size * mm / width, 0, 0, size * mm / width, 0, 0]
            )
            drawing.add(widget)
            renderPDF.draw(drawing, c, 6 * mm, 11 * mm)
        elif p.code == "code128":
            if not payload.isascii() or any(ord(ch) < 32 for ch in payload):
                raise ValueError("Code 128 : utilisez uniquement des caractères ASCII imprimables.")
            bar = code128.Code128(
                payload, barWidth=0.25 * mm, barHeight=min(12, p.height - 27) * mm
            )
            scale = min(1, (p.width - 12) * mm / bar.width)
            if 0.25 * scale < 0.18:
                raise ValueError("Code 128 trop long pour ce format. Réduisez son contenu.")
            c.setFillColor(colors.white)
            c.rect(
                5 * mm,
                12 * mm,
                min(bar.width, (p.width - 12) * mm) + 2 * mm,
                min(12, p.height - 27) * mm + 2 * mm,
                fill=1,
                stroke=0,
            )
            c.setFillColor(INK)
            c.saveState()
            c.translate(6 * mm, 13 * mm)
            c.scale(scale, 1)
            bar.drawOn(c, 0, 0)
            c.restoreState()
        c.setFillColor(colors.white)
        c.rect(
            5 * mm,
            5 * mm,
            min((p.width - 10) * mm, pdf_text_width(serial, 8, "SnackBold") + 2 * mm),
            5 * mm,
            fill=1,
            stroke=0,
        )
        c.setFillColor(INK)
        c.setFont("SnackBold", 8)
        if pdf_text_width(serial, 8, "SnackBold") > (p.width - 12) * mm:
            raise ValueError("La numérotation dépasse la largeur du support.")
        c.drawString(6 * mm, 6 * mm, serial)
        c.showPage()
    c.save()
    if files:
        with open_pdf(files[0], 1) as background, pikepdf.open(overlay) as variable:
            src = background.pages[0]
            if int(src.obj.get("/Rotate", 0)) % 360 or float(src.obj.get("/UserUnit", 1)) != 1:
                raise ValueError(
                    "Normalisez la rotation et les unités du fond PDF avant utilisation."
                )
            box = [float(v) for v in src.trimbox]
            if (
                abs((box[2] - box[0]) / mm - p.width) > 0.02
                or abs((box[3] - box[1]) / mm - p.height) > 0.02
            ):
                raise ValueError("Le format du support doit correspondre à la TrimBox du fond PDF.")
            form = src.as_form_xobject()
            form.BBox = pikepdf.Array(box)
            out = pikepdf.Pdf.new()
            for page in variable.pages:
                target = out.add_blank_page(page_size=(p.width * mm, p.height * mm))
                target.add_overlay(form, pikepdf.Rectangle(0, 0, p.width * mm, p.height * mm))
                target.add_overlay(page)
            out.save(path)
    else:
        overlay.replace(path)
    return ToolResult(
        tool="fortune-cookie",
        summary=f"{p.count} exemplaires numérotés générés.",
        metrics={"Exemplaires": p.count, "Premier numéro": p.prefix + str(p.start).zfill(p.digits)},
        warnings=[
            "Contrôler les données, le placement et la lecture des codes sur une épreuve à 100 %."
        ],
        artifacts=[artifact(path, "Série PDF personnalisée")],
    )


def pdf_text_width(text, size, font="Snack"):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    return stringWidth(text, font, size)
