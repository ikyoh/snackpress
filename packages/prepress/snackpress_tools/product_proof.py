"""Render component proofs from immutable specifications, with aligned guide layers."""

import shutil

import pikepdf
from reportlab.lib.units import mm

from .artwork_geometry import validate_page
from .common import CORAL, INK, artifact, full_page_form, new_canvas, open_pdf
from .products import snapshot_slots
from .proof_layout import BLEED_COLOR, guide_key, print_key, proof_date


def standard_guide(folder, component):
    """Basic print guides for rectangular products without a Pizza template."""
    w, h, bleed = component.width, component.height, component.bleed
    safety = min(4, w / 4, h / 4)
    path = folder / "reperes-impression.pdf"
    c = new_canvas(path, w + 2 * bleed, h + 2 * bleed)
    c.setLineWidth(0.25 * mm)
    c.setStrokeColor(CORAL)
    c.rect(bleed * mm, bleed * mm, w * mm, h * mm, fill=0)
    c.setDash(2 * mm, mm)
    c.setStrokeColor(INK)
    c.rect(
        (bleed + safety) * mm,
        (bleed + safety) * mm,
        (w - 2 * safety) * mm,
        (h - 2 * safety) * mm,
        fill=0,
    )
    if bleed:
        c.setStrokeColor(BLEED_COLOR)
        c.rect(0, 0, (w + 2 * bleed) * mm, (h + 2 * bleed) * mm, fill=0)
    c.save()
    return path, (w + 2 * bleed, h + 2 * bleed), (bleed, bleed, w, h)


def proof_canvas(page, guide):
    if guide is None:
        return
    _, (gw, gh), (ox, oy, _, _) = guide
    tx, ty = float(page.trimbox[0]), float(page.trimbox[1])
    box = pikepdf.Array([tx - ox * mm, ty - oy * mm, tx + (gw - ox) * mm, ty + (gh - oy) * mm])
    page.MediaBox = box
    page.CropBox = box


def component_guide(folder, component):
    from .burger import template
    from .catalog import Burger

    layers = (
        []
        if any(g.tool in {"pizza", "sushi"} for g in component.guides)
        else [standard_guide(folder, component)]
    )
    for index, guide in enumerate(component.guides):
        work = folder / f"trace-{index + 1}"
        work.mkdir()
        if guide.tool == "perforation":
            path = work / "perforations.pdf"
            c = new_canvas(path, component.width, component.height)
            c.setStrokeColor(CORAL)
            c.setLineWidth(0.15 * mm)
            c.setDash(2 * mm, mm)
            for position in guide.settings["positions"]:
                if guide.settings["axis"] == "vertical":
                    c.line(position * mm, 0, position * mm, component.height * mm)
                else:
                    y = (component.height - position) * mm
                    c.line(0, y, component.width * mm, y)
            c.save()
            layers.append(
                (
                    path,
                    (component.width, component.height),
                    (0, 0, component.width, component.height),
                )
            )
        else:
            layers.append(
                template(
                    work, [], Burger(template_tool=guide.tool, template_settings=guide.settings)
                )
            )
    if not layers:
        return None
    left = max(component.bleed, *(layer[2][0] for layer in layers))
    bottom = max(component.bleed, *(layer[2][1] for layer in layers))
    right = max(component.bleed, *(layer[1][0] - layer[2][0] - component.width for layer in layers))
    top = max(component.bleed, *(layer[1][1] - layer[2][1] - component.height for layer in layers))
    width, height = component.width + left + right, component.height + bottom + top
    output = pikepdf.Pdf.new()
    face_count = 1
    for path, *_ in layers:
        with pikepdf.open(path) as source:
            face_count = max(face_count, len(source.pages))
    for face in range(face_count):
        page = output.add_blank_page(page_size=(width * mm, height * mm))
        page.TrimBox = pikepdf.Array(
            [
                left * mm,
                bottom * mm,
                (left + component.width) * mm,
                (bottom + component.height) * mm,
            ]
        )
        for path, (w, h), (x, y, _, _) in layers:
            with pikepdf.open(path) as source:
                page.add_overlay(
                    full_page_form(source.pages[face % len(source.pages)]),
                    pikepdf.Rectangle(
                        (left - x) * mm,
                        (bottom - y) * mm,
                        (left - x + w) * mm,
                        (bottom - y + h) * mm,
                    ),
                )
    path = folder / "traces.pdf"
    output.save(path)
    output.close()
    return path, (width, height), (left, bottom, component.width, component.height)


def generate_product(folder, files, params, preview=False):
    from .burger import prepare
    from .catalog import Burger, ToolResult
    from .proof_render import render_proof
    from .tickets import generate_series

    snapshot = params.product_snapshot
    contract = snapshot_slots(snapshot)
    if len(files) != len(contract):
        raise ValueError(f"Ce produit attend {len(contract)} fichier(s), un par emplacement.")
    if sum(slot.pages for _, slot in contract) > 200:
        raise ValueError("Le BAT accepte au maximum 200 pages, masques compris.")
    # Normalize only proof copies; never change the uploaded production originals.
    normalized = folder / "sources-validees"
    normalized.mkdir()
    validated = []
    for index, (source, (component, slot)) in enumerate(zip(files, contract, strict=True)):
        with open_pdf(source, max_pages=200) as doc:
            if len(doc.pages) != slot.pages:
                raise ValueError(
                    f"{component.name} — {slot.name} : {slot.pages} page(s) attendue(s)."
                )
            for page in doc.pages:
                page.CropBox = validate_page(
                    page,
                    component.width,
                    component.height,
                    component.bleed,
                    f"{component.name} — {slot.name}",
                )
            target = normalized / f"source-{index}.pdf"
            doc.save(target)
            validated.append(target)
    files = validated
    proof_items = []
    extras = []

    def publish(path, label, prefix):
        target = folder / f"{prefix}-{path.name}"
        shutil.copyfile(path, target)
        return artifact(target, label)

    materials = {m.id: m.name for m in snapshot.materials}
    finishes = {f.id: f.name for f in snapshot.finishes}
    date = proof_date()
    specs = [
        ("Produit", snapshot.product_name),
        ("Date du BAT", date),
        ("Catégorie", snapshot.category_name),
        ("Déclinaison", snapshot.variant.name),
        ("Client", params.client or "Non renseigné"),
        ("Finitions", ", ".join(finishes[i] for i in snapshot.variant.finish_ids) or "Aucune"),
    ]
    for index, component in enumerate(snapshot.variant.components):
        work = folder / f"composant-{index + 1}"
        work.mkdir()
        entries = [
            (file, slot)
            for file, (comp, slot) in zip(files, contract, strict=True)
            if comp.id == component.id
        ]
        visuals = [(file, slot) for file, slot in entries if slot.role == "visual"]
        masks = [(file, slot) for file, slot in entries if slot.role == "mask"]
        guide = component_guide(work, component)
        # Match the full guide canvas while retaining the artwork's actual bleed.
        # Extra technical margins are blank; production originals remain intact.
        proof_sources = []
        labels = []
        for file_index, (file, slot) in enumerate(visuals + masks):
            with open_pdf(file, max_pages=200) as doc:
                for page in doc.pages:
                    proof_canvas(page, guide)
                target = work / f"visuel-{file_index}.pdf"
                doc.save(target)
                proof_sources.append(target)
                labels.append(f"{component.name} — {slot.name}")
        if component.tickets:
            series, manifest = generate_series(
                work, component, [file for file, _ in visuals], preview
            )
            extras += [
                publish(
                    series,
                    "Échantillon premier / dernier billet"
                    if preview
                    else "Série numérotée complète",
                    component.id,
                ),
                publish(manifest, "Numéros et carnets", component.id),
            ]
            with pikepdf.open(series) as doc:
                sample = pikepdf.Pdf.new()
                faces = len(visuals)
                indices = list(range(faces))
                if component.tickets.count > 1:
                    indices += list(range(len(doc.pages) - faces, len(doc.pages)))
                sample.pages.extend([doc.pages[i] for i in indices])
                for page in sample.pages:
                    proof_canvas(page, guide)
                target = work / "bat-premier-dernier.pdf"
                sample.save(target)
                sample.close()
            proof_sources = [target] + proof_sources[len(visuals) :]
            labels = [f"{component.name} — premier et dernier billet"] + labels[len(visuals) :]
        legacy = Burger(
            title=params.title,
            client=params.client,
            paper=materials.get(component.material_id, "À confirmer"),
            expected_files=len(proof_sources) - len(masks),
            finishes=[s.name for _, s in masks],
        )
        legend = list(
            dict.fromkeys(
                entry for g in component.guides for entry in guide_key(g.tool, g.settings)
            )
        )
        if not any(g.tool in {"pizza", "sushi"} for g in component.guides):
            legend = list(dict.fromkeys(print_key(component.bleed) + legend))
        items, _ = prepare(
            work,
            proof_sources,
            legacy,
            labels=labels,
            combined_guide=guide,
            legend=legend,
            date=date,
            finished_shape=next(
                (g.settings for g in component.guides if g.tool == "pizza"),
                next((g.settings for g in component.guides if g.tool == "sushi"), {}),
            ),
            finish_page_count=sum(s.pages for _, s in visuals),
            finish_styles=[
                f
                for f in snapshot.finishes
                if f.id in snapshot.variant.finish_ids and f.appearance.mode != "none"
            ],
            finish_masks={
                slot.id.removeprefix("mask-"): source
                for source, (_, slot) in zip(proof_sources[-len(masks) :], masks, strict=True)
            }
            if masks
            else {},
        )
        proof_items.extend(items)
        if guide:
            extras.append(publish(guide[0], f"{component.name} — tracés 1:1", component.id))
        specs += [
            (
                component.name,
                f"{component.width} × {component.height} mm ; "
                f"fond perdu {component.bleed} mm ; "
                f"{materials.get(component.material_id, 'À confirmer')}",
            )
        ]
        specs += [
            (f"{component.name} — {slot.name}", f"{slot.pages} page(s), PDF") for _, slot in entries
        ]
        specs += [(f"{component.name} — tracé {g.tool}", str(g.settings)) for g in component.guides]
    path = folder / "bat.pdf"
    render_proof(
        path,
        proof_items,
        params,
        date,
        technical_sheet=(
            specs + [("Commentaires", params.notes or "Aucun")],
            "BAT de présentation, couleurs non contractuelles. "
            "Éléments PDF natifs conservés ; simulations de finitions à 300 dpi. "
            "Spécifications figées dans les réglages JSON. "
            "Les tracés sont séparés des fichiers de production.",
        ),
    )
    return ToolResult(
        tool="burger",
        summary="BAT du produit avec fiche technique intégrée et fichiers de fabrication prêts.",
        metrics={
            "Fichiers attendus": len(contract),
            "Composants": len(snapshot.variant.components),
            "Pages du BAT": artifact(path, "BAT").pages,
        },
        artifacts=[artifact(path, "BAT A4")] + extras,
    )
