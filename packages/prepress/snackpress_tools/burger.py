"""Presentation proofs with explicit production inputs and registered template guides."""

import pikepdf
from reportlab.lib.units import mm

from .artwork_geometry import validate_page
from .catalog import MODELS, ToolResult
from .common import (
    artifact,
    dimensions,
    open_pdf,
)
from .proof_layout import guide_key, proof_date


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


def prepare(
    folder,
    files,
    p,
    labels=None,
    combined_guide=None,
    legend=None,
    date=None,
    *,
    finish_styles=None,
    finish_masks=None,
    finish_page_count=None,
    finished_shape=None,
):
    from .proof_render import ProofItem

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
    counts, sizes, trims = [], [], []
    for source in files[: len(labels)]:
        with open_pdf(source, max_pages=200) as doc:
            counts.append(len(doc.pages))
            sizes.append([dimensions(page) for page in doc.pages])
            trims.append([finished_region(page) for page in doc.pages])
    if sum(counts) > 200:
        raise ValueError("Le BAT accepte au maximum 200 pages source, finitions comprises.")
    mask_page_counts = {}
    if finish_styles is None:
        from .products import Finish

        finish_styles = [
            Finish(
                id=f"finish-{index}",
                name=name,
                mask=True,
                appearance={"mode": "area"},
            )
            for index, name in enumerate(p.finishes)
        ]
        finish_masks = {
            finish.id: files[p.expected_files + index] for index, finish in enumerate(finish_styles)
        }
        mask_page_counts = {
            finish.id: counts[p.expected_files + index]
            for index, finish in enumerate(finish_styles)
        }
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
    items = []
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
    shape = finished_shape or (p.template_settings if p.template_tool in {"pizza", "sushi"} else {})
    for file_index, (source, label, count) in enumerate(zip(files, labels, counts)):
        specs.append((label, f"Fichier {file_index + 1} — {count} page(s)"))
        visual = file_index < p.expected_files
        for index in range(count):
            w, h = sizes[file_index][index]
            trim = trims[file_index][index]
            face = (artwork_index if visual else index) % guide_faces if guide else 0
            if guide:
                full = abs(w - gw) <= 1 and abs(h - gh) <= 1
                if not full and not (abs(w - fw) <= 1 and abs(h - fh) <= 1):
                    raise ValueError(
                        f"{label}, page {index + 1} : format {w:.2f} × {h:.2f} mm incompatible "
                        f"avec le gabarit ({fw:g} × {fh:g} mm finis ou {gw:g} × {gh:g} mm à plat)."
                    )
                trim = (ox, oy, fw, fh) if full else (0, 0, w, h)
            items.append(
                ProofItem(
                    source=source,
                    source_page=index,
                    source_count=count,
                    label=label,
                    width=w,
                    height=h,
                    trim=trim,
                    visual=visual,
                    guide=guide,
                    guide_face=face,
                    legend=legend,
                    shape=shape,
                    native_guide=p.template_tool != "pdf" or combined_guide is not None,
                    finish_styles=finish_styles,
                    finish_masks=finish_masks or {},
                    mask_page_counts=mask_page_counts,
                    finish_page=artwork_index % finish_page_count
                    if finish_page_count
                    else artwork_index,
                )
            )
            if visual:
                artwork_index += 1
    return items, specs


def finished_region(page):
    """Finished rectangle in the rendered page's coordinate system, in millimetres."""
    crop, trim = page.cropbox, page.trimbox
    unit = float(page.obj.get("/UserUnit", 1)) / mm
    x, y = float(trim[0] - crop[0]) * unit, float(trim[1] - crop[1]) * unit
    w, h = float(trim[2] - trim[0]) * unit, float(trim[3] - trim[1]) * unit
    cw, ch = float(crop[2] - crop[0]) * unit, float(crop[3] - crop[1]) * unit
    if x < 0 or y < 0 or x + w > cw + 0.01 or y + h > ch + 0.01:
        return (0, 0, *dimensions(page))
    rotation = int(page.obj.get("/Rotate", 0)) % 360
    return {
        0: (x, y, w, h),
        90: (y, cw - x - w, h, w),
        180: (cw - x - w, ch - y - h, w, h),
        270: (ch - y - h, x, h, w),
    }[rotation]


def generate(folder, files, p, **options):
    if p.product_snapshot is not None:
        from .product_proof import generate_product

        return generate_product(folder, files, p)
    from .proof_render import render_proof

    paginate = options.pop("paginate", True)
    date = options.get("date") or proof_date()
    items, specs = prepare(folder, files, p, **options)
    path = folder / "bat.pdf"
    render_proof(
        path,
        items,
        p,
        date,
        paginate=paginate,
        technical_sheet=(
            specs + [("Commentaires", p.notes or "Aucun")],
            "PDF source conservés en vectoriel et images à leur résolution d’origine. "
            "Simulations de finitions à 300 dpi. Présentation au format fini, "
            "puis contrôle avec repères, puis éléments séparés avec repères vectoriels.",
        ),
    )
    return ToolResult(
        tool="burger",
        summary="BAT A4 avec fiche technique intégrée prêt.",
        metrics={
            "Faces": sum(item.visual for item in items),
            "Fichiers visuels": p.expected_files,
            "Finitions": len(p.finishes),
            "Pages du BAT": artifact(path, "BAT").pages,
        },
        artifacts=[artifact(path, "BAT A4")],
    )
