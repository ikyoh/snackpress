"""Presentation proofs with explicit production inputs and registered template guides."""

import pikepdf
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .artwork_geometry import validate_page
from .catalog import MODELS, ToolResult
from .common import (
    artifact,
    dimensions,
    full_page_form,
    new_canvas,
    open_pdf,
    paginate_pdf,
    render_page,
    report,
)
from .proof_layout import draw_legend, guide_key, header_footer, proof_date


def input_labels(p):
    if p.document_type == "card":
        labels = ["Recto", "Verso"]
    elif p.document_type == "brochure":
        labels = [f"Couverture — fichier {i + 1}" for i in range(p.cover_files)]
        labels += [f"Intérieur — fichier {i + 1}" for i in range(p.expected_files - p.cover_files)]
    else:
        labels = [f"Visuel {i + 1}" for i in range(p.expected_files)]
    return labels + [f"Finition : {name}" for name in p.finishes]


def proof_strokes(form, scale):
    """Keep native guides legible when a large format is reduced onto A4."""
    commands = []
    for operands, operator in pikepdf.parse_content_stream(form):
        if str(operator) == "w":
            operands = [max(float(operands[0]), 0.55 / scale)]
        elif str(operator) == "d" and operands[0]:
            operands = [
                pikepdf.Array(max(float(value), 1.25 / scale) for value in operands[0]),
                operands[1],
            ]
        commands.append((operands, operator))
    form.write(pikepdf.unparse_content_stream(commands))
    for child in dict(form.get("/Resources", {}).get("/XObject", {})).values():
        if child.get("/Subtype") == "/Form":
            proof_strokes(child, scale)


def template(folder, files, p):
    if p.template_tool == "none":
        return None
    if p.template_tool == "pdf":
        path = files[-1]
        with open_pdf(path, max_pages=2) as doc:
            page = doc.pages[0]
            w, h = dimensions(page)
            crop, trim = page.cropbox, page.trimbox
            for back in list(doc.pages)[1:]:
                if (
                    any(abs(a - b) > 0.01 for a, b in zip(dimensions(back), (w, h), strict=True))
                    or any(
                        abs(float(a) - float(b)) > 0.01
                        for a, b in zip(
                            list(back.cropbox) + list(back.trimbox),
                            list(crop) + list(trim),
                            strict=True,
                        )
                    )
                    or int(back.obj.get("/Rotate", 0)) % 360
                    != int(page.obj.get("/Rotate", 0)) % 360
                    or float(back.obj.get("/UserUnit", 1)) != float(page.obj.get("/UserUnit", 1))
                ):
                    raise ValueError(
                        "Les deux faces du gabarit PDF doivent avoir les mêmes formats "
                        "et boîtes de page."
                    )
            if int(page.obj.get("/Rotate", 0)) % 360 == 0:
                unit = float(page.obj.get("/UserUnit", 1)) / mm
                ox, oy = float(trim[0] - crop[0]) * unit, float(trim[1] - crop[1]) * unit
                fw, fh = float(trim[2] - trim[0]) * unit, float(trim[3] - trim[1]) * unit
                if ox >= 0 and oy >= 0 and ox + fw <= w + 0.01 and oy + fh <= h + 0.01:
                    return path, (w, h), (ox, oy, fw, fh)
        return path, (w, h), (0, 0, w, h)
    from .generators import burrito, pizza, sushi, taco

    settings = MODELS[p.template_tool].model_validate(p.template_settings)
    work = folder / "gabarit-burger"
    work.mkdir()
    result = {"pizza": pizza, "taco": taco, "burrito": burrito, "sushi": sushi}[p.template_tool](
        work, [], settings, **({"guides_only": True} if p.template_tool == "taco" else {})
    )
    path = work / result.artifacts[0].name
    # Keep vector strokes (cut, fold, safety, eyelets); omit fills and panel labels.
    with pikepdf.open(path, allow_overwriting_input=True) as doc:
        for page in doc.pages:
            commands, in_text = [], False
            for operands, operator in pikepdf.parse_content_stream(page):
                op = str(operator)
                if op == "BT":
                    in_text = True
                elif op == "ET":
                    in_text = False
                elif not in_text:
                    if op in {"f", "F", "f*"}:
                        operator = pikepdf.Operator("n")
                    elif op in {"B", "B*", "b", "b*"}:
                        operator = pikepdf.Operator("S" if op.startswith("B") else "s")
                    commands.append((operands, operator))
            page.Contents = doc.make_stream(pikepdf.unparse_content_stream(commands))
        w, h = dimensions(doc.pages[0])
        doc.save(path)
    origin = (
        settings.bleed
        if p.template_tool == "pizza"
        else 15
        if p.template_tool == "taco"
        else 5
        if p.template_tool == "sushi"
        else 0
    )
    return path, (w, h), (origin, origin, settings.width, settings.height)


def generate(
    folder,
    files,
    p,
    labels=None,
    combined_guide=None,
    legend=None,
    date=None,
    *,
    paginate=True,
    finish_styles=(),
    finish_masks=None,
    finish_page_count=None,
):
    if p.product_snapshot is not None:
        from .product_proof import generate_product

        return generate_product(folder, files, p)
    labels = labels if labels is not None else input_labels(p)
    expected = len(labels) + (p.template_tool == "pdf")
    if len(files) != expected:
        raise ValueError(
            f"BAT : {expected} fichier(s) attendu(s) : {p.expected_files} visuel(s), "
            f"{len(p.finishes)} finition(s) et {int(p.template_tool == 'pdf')} gabarit PDF."
        )
    if p.template_tool == "pizza":
        settings = MODELS["pizza"].model_validate(p.template_settings)
        normalized = folder / "sources-validees"
        normalized.mkdir()
        validated = []
        for index, source in enumerate(files):
            with open_pdf(source, max_pages=200) as doc:
                for number, page in enumerate(doc.pages, 1):
                    page.CropBox = validate_page(
                        page,
                        settings.width,
                        settings.height,
                        settings.bleed,
                        f"{labels[index]}, page {number}",
                    )
                target = normalized / f"source-{index}.pdf"
                doc.save(target)
                validated.append(target)
        files = validated
    counts, sizes = [], []
    for source in files[: len(labels)]:
        with open_pdf(source, max_pages=200) as doc:
            counts.append(len(doc.pages))
            sizes.append([dimensions(page) for page in doc.pages])
    if sum(counts) > 200:
        raise ValueError("Le BAT accepte au maximum 200 pages source, finitions comprises.")
    if p.document_type == "card" and counts[:2] != [1, 1]:
        raise ValueError("La carte recto verso attend deux PDF d’une page chacun.")
    if p.document_type == "brochure":
        if sum(counts[: p.cover_files]) != 4:
            raise ValueError("La couverture de la brochure doit contenir exactement 4 pages.")
        if sum(counts[p.cover_files : p.expected_files]) != p.interior_pages:
            raise ValueError(f"L’intérieur doit contenir exactement {p.interior_pages} pages.")
    guide = combined_guide or template(folder, files, p)
    date = date or proof_date()
    legend = (
        legend
        if legend is not None
        else guide_key(p.template_tool, p.template_settings)
        if guide
        else []
    )
    if guide:
        guide_path, (gw, gh), (ox, oy, fw, fh) = guide
        with open_pdf(guide_path, max_pages=2) as doc:
            guide_faces = len(doc.pages)
    path = folder / "bat.pdf"
    c = new_canvas(path, 210, 297)
    guide_placements = []
    page_index = 0
    artwork_index = 0
    specs = [
        ("Projet", p.title),
        ("Date du BAT", date),
        ("Client", p.client or "Non renseigné"),
        ("Papier", p.paper),
        ("Fichiers visuels attendus / reçus", f"{p.expected_files} / {p.expected_files}"),
        ("Gabarit", p.template_tool),
        ("Finitions", ", ".join(p.finishes) or "Aucune"),
    ]
    for file_index, (source, label, count) in enumerate(zip(files, labels, counts)):
        specs.append((label, f"Fichier {file_index + 1} — {count} page(s)"))
        for index in range(count):
            w, h = sizes[file_index][index]
            dpi = min(120, 1100 * 25.4 / max(w, h))
            image, _ = render_page(source, index, dpi=dpi)
            has_finishes = bool(finish_styles) and file_index < p.expected_files
            marked = guide is not None
            # Each finish file starts with its own recto; simulations share the
            # artwork's face without advancing the recto/verso sequence.
            face_index = artwork_index if file_index < p.expected_files else index
            guide_face = face_index % guide_faces if marked else 0
            full = marked and abs(w - gw) <= 1 and abs(h - gh) <= 1
            if marked and not full and not (abs(w - fw) <= 1 and abs(h - fh) <= 1):
                raise ValueError(
                    f"{label}, page {index + 1} : format {w:.2f} × {h:.2f} mm incompatible "
                    f"avec le gabarit ({fw:g} × {fh:g} mm finis ou {gw:g} × {gh:g} mm à plat)."
                )
            views = [False]
            if has_finishes:
                views.append(True)
            for with_finishes in views:
                with_guides = marked
                bw, bh = (gw, gh) if with_guides else (w, h)
                bottom = 65 + max(0, (len(legend) + 1) // 2 - 2) * 5 if with_guides else 65
                height = 249 - bottom
                scale = min(174 / bw, height / bh)
                x, y = (210 - bw * scale) / 2, bottom + (height - bh * scale) / 2
                header_footer(c, date)
                c.setFillColor(colors.black)
                c.setFont("SnackDisplay", 18)
                c.drawString(18 * mm, 267 * mm, p.title)
                c.setFont("Snack", 9)
                c.drawString(18 * mm, 260 * mm, f"{label} — page {index + 1} / {count}")
                view_label = (
                    "Simulation des finitions"
                    if with_finishes
                    else "Contrôle de finition"
                    if file_index >= p.expected_files
                    else "Visuel"
                )
                c.drawString(
                    18 * mm,
                    254 * mm,
                    (
                        f"{view_label} avec repères — {'Recto' if guide_face == 0 else 'Verso'}"
                        if guide_faces == 2
                        else f"{view_label} avec repères de gabarit"
                    )
                    if with_guides
                    else "Simulation des finitions"
                    if with_finishes
                    else "Visuel seul",
                )
                ix, iy = (ox, oy) if with_guides and not full else (0, 0)
                displayed = image
                if with_finishes:
                    from .finish_appearance import simulate_finishes

                    displayed = simulate_finishes(
                        image,
                        finish_styles,
                        finish_masks or {},
                        artwork_index % finish_page_count if finish_page_count else artwork_index,
                        dpi,
                    )
                    if full:
                        # Finishes cover the finished product. Keep the real bleed
                        # and the guide's technical margins unchanged in simulations.
                        trim_pixels = (
                            round(ox / gw * image.width),
                            round((gh - oy - fh) / gh * image.height),
                            round((ox + fw) / gw * image.width),
                            round((gh - oy) / gh * image.height),
                        )
                        simulation = displayed
                        displayed = image.copy()
                        displayed.paste(simulation.crop(trim_pixels), trim_pixels)
                    c.setFont("Snack", 8)
                    c.drawString(
                        18 * mm,
                        (43 if with_guides else 49) * mm,
                        "Finitions : " + ", ".join(f.name for f in finish_styles)[:110],
                    )
                c.drawImage(
                    ImageReader(displayed),
                    (x + ix * scale) * mm,
                    (y + iy * scale) * mm,
                    width=w * scale * mm,
                    height=h * scale * mm,
                )
                if with_guides:
                    draw_legend(c, legend, bottom)
                    guide_placements.append(
                        (
                            page_index,
                            pikepdf.Rectangle(
                                x * mm, y * mm, (x + gw * scale) * mm, (y + gh * scale) * mm
                            ),
                            guide_face,
                        )
                    )
                c.setFont("Snack", 8)
                c.drawString(18 * mm, 38 * mm, "BAT DE PRÉSENTATION — COULEURS NON CONTRACTUELLES")
                c.drawString(
                    18 * mm,
                    31 * mm,
                    f"Source : {w:.2f} × {h:.2f} mm ; aperçu à {scale * 100:.1f} %",
                )
                c.drawString(18 * mm, 22 * mm, f"Client : {p.client[:75] or 'Non renseigné'}")
                c.showPage()
                page_index += 1
            if file_index < p.expected_files:
                artwork_index += 1
    c.save()
    if guide_placements:
        with (
            open_pdf(guide_path, max_pages=2) as source,
            pikepdf.open(path, allow_overwriting_input=True) as proof,
        ):
            # Import native PDF objects once; reuse the form on all marked pages.
            forms = [proof.copy_foreign(full_page_form(page)) for page in source.pages]
            if p.template_tool != "pdf" or combined_guide is not None:
                guide_scale = float(guide_placements[0][1].width) / (gw * mm)
                for form in forms:
                    proof_strokes(form, guide_scale)
            # Generated guides contain strokes only. Normal blending keeps their
            # colors visible over dark artwork; imported PDFs may contain white fills.
            blending = pikepdf.Dictionary(
                Type=pikepdf.Name.ExtGState,
                BM=pikepdf.Name.Multiply
                if p.template_tool == "pdf" and combined_guide is None
                else pikepdf.Name.Normal,
            )
            for index, rect, guide_face in guide_placements:
                form = forms[guide_face]
                page = proof.pages[index]
                state_name = page.add_resource(blending, pikepdf.Name.ExtGState)
                form_name = page.add_resource(form, pikepdf.Name.XObject)
                placement = page.calc_form_xobject_placement(
                    form, form_name, rect, allow_shrink=True, allow_expand=True
                )
                page.contents_add(
                    b"q\n" + str(state_name).encode("ascii") + b" gs\n" + placement + b"\nQ\n"
                )
            proof.save(path)
    if paginate:
        paginate_pdf(path)
    sheet = folder / "fiche-technique.pdf"
    report(
        sheet,
        "Fiche technique du BAT",
        specs + [("Commentaires", p.notes or "Aucun")],
        "Visuels rasterisés pour la présentation. Repères PDF conservés en vectoriel "
        "et superposés à l’échelle du document. "
        "Chaque finition dispose de son propre fichier et de ses pages de contrôle.",
    )
    return ToolResult(
        tool="burger",
        summary="BAT A4 et fiche technique prêts.",
        metrics={
            "Faces": sum(counts[: p.expected_files]),
            "Fichiers visuels": p.expected_files,
            "Finitions": len(p.finishes),
            "Pages du BAT": artifact(path, "BAT").pages,
        },
        artifacts=[artifact(path, "BAT A4"), artifact(sheet, "Fiche technique")],
    )
