from contextlib import ExitStack
from math import ceil

import pikepdf
from reportlab.lib import colors
from reportlab.lib.colors import CMYKColorSep
from reportlab.lib.units import mm

from .artwork_geometry import validate_page
from .catalog import Repiquage, ToolResult
from .common import CORAL, INK, artifact, new_canvas, open_pdf, report
from .fortune_data import draw_repiquage, value_at
from .products import finish_placement_rows
from .taco_layout import fold_widths as fold_widths


def burger(folder, files, p):
    from .burger import generate

    return generate(folder, files, p)


def pizza(folder, files, p, *, guides_only=False):
    path = folder / "gabarit.pdf"
    w, h = p.width + 2 * p.bleed, p.height + 2 * p.bleed
    c = new_canvas(path, w, h)

    def contour(left=0, right=0, top=0, bottom=0):
        x, y = (p.bleed + left) * mm, (p.bleed + bottom) * mm
        width, height = (p.width - left - right) * mm, (p.height - top - bottom) * mm
        path = c.beginPath()
        if p.shape in {"circle", "ellipse"}:
            path.ellipse(x, y, width, height)
        elif p.corner_radius > 0:
            radius = min(
                max(0, p.corner_radius - max(left, right, top, bottom)) * mm, width / 2, height / 2
            )
            path.roundRect(x, y, width, height, radius)
        else:
            path.rect(x, y, width, height)
        return path

    cut = contour()
    if not guides_only:
        c.setFillColor(colors.HexColor("#f7e5dc"))
        c.drawPath(contour(*([-p.bleed] * 4)), fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.drawPath(cut, fill=1, stroke=0)

    left, right, top, bottom = (
        getattr(p, f"unusable_{side}") for side in ("left", "right", "top", "bottom")
    )
    if any((left, right, top, bottom)):
        c.saveState()
        c.clipPath(cut, fill=0, stroke=0)
        # Clip to the union of edge bands, so corner overlaps hatch only once.
        bands = c.beginPath()
        bands.rect(p.bleed * mm, p.bleed * mm, p.width * mm, p.height * mm)
        bands.rect(
            (p.bleed + left) * mm,
            (p.bleed + bottom) * mm,
            (p.width - left - right) * mm,
            (p.height - top - bottom) * mm,
        )
        c.saveState()
        c.clipPath(bands, fill=0, stroke=0, fillMode=0)
        c.setStrokeColor(colors.HexColor("#e6b800"))
        c.setLineWidth(0.18 * mm)
        for index in range(-ceil(p.height / 3), ceil(p.width / 3) + 1):
            x = p.bleed + index * 3
            c.line(x * mm, p.bleed * mm, (x + p.height) * mm, (p.bleed + p.height) * mm)
        c.restoreState()
        c.setStrokeColor(colors.HexColor("#e6b800"))
        c.setLineWidth(0.3 * mm)
        c.setDash(2 * mm, 1 * mm)
        x0, x1 = (p.bleed + left) * mm, (p.bleed + p.width - right) * mm
        y0, y1 = (p.bleed + bottom) * mm, (p.bleed + p.height - top) * mm
        if left:
            c.line(x0, y0, x0, y1)
        if right:
            c.line(x1, y0, x1, y1)
        if bottom:
            c.line(x0, y0, x1, y0)
        if top:
            c.line(x0, y1, x1, y1)
        c.restoreState()

    c.saveState()
    c.clipPath(cut, fill=0, stroke=0)
    c.setStrokeColor(INK)
    c.setLineWidth(0.25 * mm)
    c.setDash(2 * mm, 1 * mm)
    c.drawPath(contour(p.safety_left, p.safety_right, p.safety_top, p.safety_bottom))
    c.restoreState()
    c.setStrokeColor(CORAL)
    c.setLineWidth(0.25 * mm)
    c.drawPath(cut)
    if p.bleed:
        c.setStrokeColor(colors.HexColor("#3265c9"))
        c.setDash(2 * mm, mm)
        c.drawPath(contour(*([-p.bleed] * 4)))
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
            (
                "Forme",
                {"circle": "Ronde", "ellipse": "Ovale"}.get(p.shape, "Carrée / rectangulaire"),
            ),
            ("Format fini", f"{p.width} × {p.height} mm"),
            (
                "Rayon des coins",
                "Sans objet" if p.shape != "rectangle" else f"{p.corner_radius} mm",
            ),
            ("Fond perdu", f"{p.bleed} mm, zone saumon et contour bleu pointillé"),
            (
                "Sécurité (haut / bas / gauche / droite)",
                f"{p.safety_top:g} / {p.safety_bottom:g} / "
                f"{p.safety_left:g} / {p.safety_right:g} mm, "
                "trait vert pointillé",
            ),
            (
                "Zone inexploitable (haut / bas / gauche / droite)",
                f"{p.unusable_top:g} / {p.unusable_bottom:g} / "
                f"{p.unusable_left:g} / {p.unusable_right:g} mm, "
                "limite jaune pointillée et hachures diagonales",
            ),
            ("Coupe", "Trait corail continu ; TrimBox rectangulaire englobante"),
        ],
        "Guides visibles : gabarit de préparation, à retirer du document final.",
    )
    return ToolResult(
        tool="pizza",
        summary="Gabarit à taille réelle avec TrimBox et BleedBox.",
        metrics={"Largeur finie (mm)": p.width, "Hauteur finie (mm)": p.height},
        artifacts=[artifact(path, "Gabarit PDF 1:1"), artifact(sheet, "Légende des guides")],
    )


def taco(folder, files, p, *, guides_only=False):
    from .taco_layout import (
        FOLD_NAMES,
        TURN_NAMES,
        face_label,
        face_panels,
        fold_positions,
        reference_corner,
    )

    path = folder / "plan-pliage.pdf"
    border = 15
    page_width, page_height = p.width + 2 * border, p.height + 2 * border
    c = new_canvas(path, page_width, page_height)

    def fitted(text, x, y, width, size=8, font="Snack", centered=False):
        c.setFont(font, min(size, width * mm / max(c.stringWidth(text, font, 1), 1)))
        draw = c.drawCentredString if centered else c.drawString
        draw(x * mm, y * mm, text)

    for page_number, face in enumerate(("recto", "verso"), 1):
        panels = face_panels(p, face)
        x = border
        for panel in panels:
            if not guides_only:
                c.setFillColor(colors.HexColor("#eef1e7") if panel.number % 2 else colors.white)
                c.rect(x * mm, border * mm, panel.width * mm, p.height * mm, stroke=0, fill=1)
                c.setFillColor(colors.black)
                middle = border + p.height / 2
                fitted(
                    f"P{panel.number}",
                    x + panel.width / 2,
                    middle + 4,
                    panel.width - 2,
                    12,
                    centered=True,
                )
                fitted(
                    f"{panel.width:g} mm",
                    x + panel.width / 2,
                    middle - 2,
                    panel.width - 2,
                    9,
                    centered=True,
                )
                if panel.flap:
                    fitted(
                        "Rabat rentrant",
                        x + panel.width / 2,
                        middle - 8,
                        panel.width - 2,
                        8,
                        centered=True,
                    )
            x += panel.width
        # Paint folds after all panel backgrounds, so the next panel cannot hide them.
        c.setStrokeColor(INK)
        c.setLineWidth(0.25 * mm)
        c.rect(border * mm, border * mm, p.width * mm, p.height * mm)
        c.setStrokeColor(CORAL)
        c.setDash(3 * mm, 2 * mm)
        for position in fold_positions(p, face):
            x = (border + position) * mm
            c.line(x, border * mm, x, (border + p.height) * mm)
        c.setDash()
        if not guides_only:
            c.setFillColor(colors.black)
            fitted(
                f"Taco — {face_label(p, face)}",
                4,
                page_height - 5,
                page_width - 8,
                14,
                "SnackDisplay",
            )
            fitted(
                f"{FOLD_NAMES[p.fold]} · Retournement : {TURN_NAMES[p.turn]}",
                4,
                page_height - 10,
                page_width - 8,
                8,
            )
            # A marks the same physical corner after either kind of paper turn.
            ax, ay = reference_corner(p, face)
            c.circle((border + ax) * mm, (border + ay) * mm, 0.8 * mm, stroke=0, fill=1)
            fitted("A", border + ax + (2 if ax == 0 else -3), border + ay + (2 if ay else -4), 4, 8)
            fitted("Repère A : même coin de feuille sur les deux faces.", 4, 9, page_width - 8, 7)
            fitted(
                "Plis corail pointillés ; cotes depuis le bord gauche de cette face.",
                4,
                5.5,
                page_width - 8,
                7,
            )
            c.setFont("Snack", 7)
            c.drawRightString((page_width - 4) * mm, 2 * mm, f"Page {page_number} / 2")
        c.showPage()
    c.save()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for page in pdf.pages:
            page.TrimBox = pikepdf.Array(
                [border * mm, border * mm, (border + p.width) * mm, (border + p.height) * mm]
            )
        pdf.save(path)
    sheet = folder / "fiche-pliage.pdf"
    rows = [
        ("Type de pli", FOLD_NAMES[p.fold]),
        ("Format à plat", f"{p.width:g} × {p.height:g} mm"),
        ("Recto / verso", f"{face_label(p, 'recto')} ; {face_label(p, 'verso')}"),
        ("Retournement du verso", TURN_NAMES[p.turn]),
        ("Repère A", "Coin haut gauche du recto, identifié sur les deux faces."),
        ("Retrait", "Sans objet en accordéon" if p.fold == "accordion" else f"{p.allowance:g} mm"),
    ]
    for face in ("recto", "verso"):
        panels = face_panels(p, face)
        rows += [
            (
                f"Panneaux {face}, de gauche à droite",
                "; ".join(
                    f"P{panel.number} : {panel.width:g} mm"
                    + (" (rabat rentrant)" if panel.flap else "")
                    for panel in panels
                ),
            ),
            (
                f"Plis {face} depuis le bord gauche",
                " / ".join(f"{position:g} mm" for position in fold_positions(p, face)),
            ),
        ]
    report(
        sheet,
        "Taco — plan de panneaux",
        rows,
        "P1, P2… identifient les mêmes panneaux physiques sur les deux faces, "
        "sans imposer l’ordre de lecture. Schéma indicatif, sans simulation de pliage. "
        "Valider retraits et faces avec le façonnier.",
    )
    return ToolResult(
        tool="taco",
        summary=f"Plan recto / verso de {len(panels)} panneaux, avec repères correspondants.",
        metrics={"Panneaux": len(panels), "Largeur totale (mm)": p.width, "Faces": 2},
        artifacts=[artifact(path, "Plan recto / verso 1:1"), artifact(sheet, "Fiche des panneaux")],
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
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].TrimBox = pikepdf.Array([0, 0, p.width * mm, p.height * mm])
        pdf.save(path)
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
        branded_header=True,
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
    path = folder / "contours.pdf"
    pad = p.bleed
    c = new_canvas(path, p.width + 2 * pad, p.height + 2 * pad)
    c.setLineWidth(0.1 * mm)
    c.setStrokeOverprint(True)
    c.setStrokeColor(CMYKColorSep(0, 100, 0, 0, spotName=p.cut_name))
    if p.shape == "circle":
        c.circle((pad + p.width / 2) * mm, (pad + p.height / 2) * mm, p.width / 2 * mm)
    elif p.shape == "rectangle":
        if p.corner_radius:
            c.roundRect(pad * mm, pad * mm, p.width * mm, p.height * mm, p.corner_radius * mm)
        else:
            c.rect(pad * mm, pad * mm, p.width * mm, p.height * mm)
    for line in p.lines:
        c.setStrokeColor(
            CMYKColorSep(0, 100, 0, 0, spotName=p.cut_name)
            if line.kind == "cut"
            else CMYKColorSep(100, 0, 0, 0, spotName=p.crease_name)
        )
        if line.axis == "vertical":
            x = (pad + line.position) * mm
            c.line(x, pad * mm, x, (pad + p.height) * mm)
        else:
            y = (pad + p.height - line.position) * mm
            c.line(pad * mm, y, (pad + p.width) * mm, y)
    c.save()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        page.TrimBox = pikepdf.Array(
            [pad * mm, pad * mm, (pad + p.width) * mm, (pad + p.height) * mm]
        )
        page.BleedBox = page.MediaBox
        pdf.save(path)
    sheet = folder / "convention.pdf"
    report(
        sheet,
        "Sushi — convention de tracé",
        [
            ("Format fini", f"{p.width} × {p.height} mm"),
            ("Format du PDF", f"{p.width + 2 * p.bleed:g} × {p.height + 2 * p.bleed:g} mm"),
            ("Contour", {"none": "Aucun", "rectangle": "Rectangle", "circle": "Cercle"}[p.shape]),
            (
                "Rayon des coins",
                f"{p.corner_radius:g} mm" if p.shape == "rectangle" else "Sans objet",
            ),
            ("Fond perdu", f"{p.bleed:g} mm sur chaque côté, défini par la BleedBox"),
            ("Découpe", p.cut_name),
            ("Rainage", p.crease_name),
            *[
                (
                    f"Tracé {index}",
                    f"{'Coupe' if line.kind == 'cut' else 'Rainage'} "
                    f"{'vertical' if line.axis == 'vertical' else 'horizontal'} · "
                    f"{line.position:g} mm depuis "
                    f"{'la gauche' if line.axis == 'vertical' else 'le haut'} du format fini",
                )
                for index, line in enumerate(p.lines, 1)
            ],
            ("Trait", "Vectoriel 0,1 mm, sans remplissage, surimpression activée"),
            ("Origine du format fini", f"{pad:g} mm depuis les bords de la page"),
        ],
        (
            "Confirmer les noms de tons directs, l’épaisseur de trait et la "
            "surimpression avec l’atelier avant utilisation."
        ),
    )
    return ToolResult(
        tool="sushi",
        summary="Contours vectoriels en deux tons directs nommés.",
        metrics={
            "Rainages": sum(line.kind == "crease" for line in p.lines),
            "Coupes": sum(line.kind == "cut" for line in p.lines),
        },
        artifacts=[
            artifact(path, "Contours PDF vectoriels"),
            artifact(sheet, "Convention atelier"),
        ],
    )


def kebab(folder, files, p):
    path = folder / "fiche-fabrication.pdf"
    snapshot = p.product_snapshot
    materials = {m.id: m for m in snapshot.materials}
    finishes = {f.id: f.name for f in snapshot.finishes}
    rows = [
        ("Client / projet", p.client or "Non renseigné"),
        ("Produit", snapshot.product_name),
        ("Catégorie", snapshot.category_name),
        ("Déclinaison", snapshot.variant.name),
        ("Quantité", f"{p.quantity} exemplaires"),
        ("Couleurs", p.colors),
        ("Finitions", ", ".join(finishes[i] for i in snapshot.variant.finish_ids) or "Aucune"),
    ]
    guide_names = {
        "pizza": "Découpe",
        "taco": "Pliage",
        "burrito": "Ourlets et œillets",
        "sushi": "Découpe et rainage",
        "perforation": "Perforation",
    }
    for component in snapshot.variant.components:
        material = materials.get(component.material_id)
        support = "À confirmer"
        if material:
            details = [material.name, material.family]
            if material.gsm is not None:
                details.append(f"{material.gsm:g} g/m²")
            if material.thickness is not None:
                details.append(f"Épaisseur : {material.thickness:g} mm")
            if material.description:
                details.append(material.description)
            support = " · ".join(details)
        rows.extend(
            [
                ("Composant", component.name),
                ("Format fini", f"{component.width:g} × {component.height:g} mm"),
                ("Fond perdu", f"{component.bleed:g} mm sur chaque côté"),
                ("Support matière", support),
                (
                    "Faces / pagination",
                    "\n".join(
                        f"{s.name} : {s.pages} page(s)" + (" — masque" if s.role == "mask" else "")
                        for s in component.slots
                    ),
                ),
            ]
        )
        if component.pizza_template:
            template = component.pizza_template
            rows.append(("Gabarit", f"{template.name} · révision {template.revision}"))
        rows.extend(finish_placement_rows(snapshot, component))
        for guide in component.guides:
            s = guide.settings
            if guide.tool == "pizza":
                shapes = {"rectangle": "Rectangle", "circle": "Cercle", "ellipse": "Ellipse"}
                detail = f"{shapes[s['shape']]} · rayon des coins : {s['corner_radius']:g} mm"
            elif guide.tool == "taco":
                folds = {"accordion": "Accordéon", "roll": "Roulé", "gate": "Fenêtre"}
                detail = (
                    f"{folds[s['fold']]} · {s['panels']} panneaux · retrait : {s['allowance']:g} mm"
                )
            elif guide.tool == "burrito":
                detail = (
                    f"Ourlet : {s['hem']:g} mm · fourreau : {s['sleeve']:g} mm"
                    f" · espacement des œillets : {s['spacing']:g} mm"
                    f" · retrait des œillets : {s['inset']:g} mm"
                )
            elif guide.tool == "sushi":
                shape = {"none": "Aucun", "rectangle": "Rectangle", "circle": "Cercle"}[s["shape"]]
                detail = (
                    f"Ton de découpe : {s['cut_name']} · rainage : {s['crease_name']}"
                    f" · contour : {shape} · fond perdu : {s['bleed']:g} mm"
                )
                if s["shape"] == "rectangle":
                    detail += f" · rayon des coins : {s['corner_radius']:g} mm"
                for index, line in enumerate(s["lines"], 1):
                    rows.append(
                        (
                            f"Sushi — tracé {index}",
                            f"{'Coupe' if line['kind'] == 'cut' else 'Rainage'} · "
                            f"{'vertical' if line['axis'] == 'vertical' else 'horizontal'} · "
                            f"{line['position']:g} mm depuis "
                            f"{'la gauche' if line['axis'] == 'vertical' else 'le haut'}",
                        )
                    )
            else:
                axis = "verticales" if s["axis"] == "vertical" else "horizontales"
                detail = f"Positions {axis} : " + ", ".join(f"{x:g} mm" for x in s["positions"])
            rows.append((guide_names[guide.tool], detail))
        if component.tickets:
            tickets = component.tickets
            binding = {"loose": "Feuilles libres", "stapled": "Agrafé", "glued": "Collé"}
            first = tickets.prefix + str(tickets.start).zfill(tickets.digits) + tickets.suffix
            last = (
                tickets.prefix
                + str(tickets.start + tickets.count - 1).zfill(tickets.digits)
                + tickets.suffix
            )
            rows.append(
                (
                    "Billets numérotés",
                    (
                        f"{first} à {last} · {tickets.count} billets"
                        f" · {tickets.per_book} par carnet"
                        f" · {binding[tickets.binding]}"
                    ),
                )
            )
    rows.append(("Consignes", p.notes or "Aucune"))
    report(
        path,
        p.title,
        rows,
        (
            "Fiche d’instructions déclaratives : aucune validation automatique"
            " des choix de fabrication."
        ),
        branded_header=True,
    )
    return ToolResult(
        tool="kebab",
        summary="Fiche d’instructions prête pour l’atelier.",
        artifacts=[artifact(path, "Fiche de fabrication")],
    )


def fortune(folder, files, p, *, preview=False):
    path = folder / "serie.pdf"
    overlay = folder / "variable.pdf"
    bleed = p.bleed * mm
    full_width, full_height = (p.width + 2 * p.bleed) * mm, (p.height + 2 * p.bleed) * mm
    c = new_canvas(overlay, p.width + 2 * p.bleed, p.height + 2 * p.bleed)
    for index in range(p.count):
        c.saveState()
        c.translate(bleed, bleed)
        clip = c.beginPath()
        clip.rect(0, 0, p.width * mm, p.height * mm)
        c.clipPath(clip, stroke=0, fill=0)
        repiquages = p.repiquages if p.repiquages is not None else [Repiquage(y=p.height - 6)]
        for item in repiquages:
            c.saveState()
            c.translate(item.x * mm, (p.height - item.y) * mm)
            c.rotate(-item.rotation)
            c.setFillColor(colors.HexColor(item.color))
            draw_repiquage(c, item, value_at(p, item, index))
            c.restoreState()
        c.restoreState()
        c.showPage()
    c.save()
    with ExitStack() as stack:
        variable = stack.enter_context(pikepdf.open(overlay))
        out = pikepdf.Pdf.new()
        background_form = None
        if files:
            background = stack.enter_context(open_pdf(files[0], 1))
            src = background.pages[0]
            if int(src.obj.get("/Rotate", 0)) % 360 or float(src.obj.get("/UserUnit", 1)) != 1:
                raise ValueError(
                    "Normalisez la rotation et les unités du fond PDF avant utilisation."
                )
            region = validate_page(src, p.width, p.height, p.bleed, "Fond PDF Fortune Cookie")
            box = list(map(float, src.trimbox))
            background_form = out.copy_foreign(src.as_form_xobject())
            background_form.BBox = region
            background_form.Matrix = pikepdf.Array([1, 0, 0, 1, 0, 0])
        for page in variable.pages:
            if background_form is None:
                out.pages.append(page)
                target = out.pages[-1]
            else:
                target = out.add_blank_page(page_size=(full_width, full_height))
                name = target.add_resource(background_form, pikepdf.Name.XObject)
                # Keep the artwork at its native scale, including non-zero page origins.
                target.contents_add(
                    f"q 1 0 0 1 {bleed - box[0]:.8f} {bleed - box[1]:.8f} cm {name} Do Q".encode()
                )
                target.add_overlay(page, pikepdf.Rectangle(0, 0, full_width, full_height))
            target.TrimBox = pikepdf.Array(
                [bleed, bleed, bleed + p.width * mm, bleed + p.height * mm]
            )
            target.BleedBox = target.MediaBox
        out.save(path)
    if p.layer_template:
        from .fortune_imposition import impose

        artifacts, metrics, warnings = impose(folder, path, p, preview=preview)
        return ToolResult(
            tool="fortune-cookie",
            summary=f"{p.count} billets imposés pour {metrics['Souches']} souche(s).",
            metrics=metrics,
            warnings=warnings,
            artifacts=artifacts,
        )
    return ToolResult(
        tool="fortune-cookie",
        summary=f"{p.count} exemplaires avec repiquages générés.",
        metrics={
            "Exemplaires": p.count,
            "Repiquages": len(p.repiquages) if p.repiquages is not None else 1,
            **(
                {"Premier numéro": p.prefix + str(p.start).zfill(p.digits)}
                if p.repiquages is None or any(item.source == "sequence" for item in p.repiquages)
                else {}
            ),
        },
        warnings=[
            "Contrôler les repiquages, les codes-barres, le placement et le fond perdu "
            "sur une épreuve à 100 %."
        ],
        artifacts=[artifact(path, "Série PDF personnalisée")],
    )
