"""Render component proofs from immutable specifications, with aligned guide layers."""

import shutil

import pikepdf
from reportlab.lib.units import mm

from .common import CORAL, artifact, new_canvas, open_pdf, report
from .products import snapshot_slots
from .proof_layout import guide_key, proof_date


def component_guide(folder, component):
    from .burger import template
    from .catalog import Burger

    layers = []
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
    left = max(layer[2][0] for layer in layers)
    bottom = max(layer[2][1] for layer in layers)
    right = max(layer[1][0] - layer[2][0] - component.width for layer in layers)
    top = max(layer[1][1] - layer[2][1] - component.height for layer in layers)
    width, height = component.width + left + right, component.height + bottom + top
    output = pikepdf.Pdf.new()
    page = output.add_blank_page(page_size=(width * mm, height * mm))
    page.TrimBox = pikepdf.Array(
        [left * mm, bottom * mm, (left + component.width) * mm, (bottom + component.height) * mm]
    )
    for path, (w, h), (x, y, _, _) in layers:
        with pikepdf.open(path) as source:
            page.add_overlay(
                source.pages[0],
                pikepdf.Rectangle(
                    (left - x) * mm, (bottom - y) * mm, (left - x + w) * mm, (bottom - y + h) * mm
                ),
            )
    path = folder / "traces.pdf"
    output.save(path)
    output.close()
    return path, (width, height), (left, bottom, component.width, component.height)


def generate_product(folder, files, params, preview=False):
    from .burger import generate
    from .catalog import Burger, ToolResult
    from .tickets import generate_series

    snapshot = params.product_snapshot
    contract = snapshot_slots(snapshot)
    if len(files) != len(contract):
        raise ValueError(f"Ce produit attend {len(contract)} fichier(s), un par emplacement.")
    if sum(slot.pages for _, slot in contract) > 200:
        raise ValueError("Le BAT accepte au maximum 200 pages, masques compris.")
    # Verify every file before producing output. Compare physical TrimBox, not the media size.
    for source, (component, slot) in zip(files, contract, strict=True):
        with open_pdf(source, max_pages=200) as doc:
            if len(doc.pages) != slot.pages:
                raise ValueError(
                    f"{component.name} — {slot.name} : {slot.pages} page(s) attendue(s)."
                )
            for page in doc.pages:
                if (
                    int(page.obj.get("/Rotate", 0)) % 360
                    or float(page.obj.get("/UserUnit", 1)) != 1
                ):
                    raise ValueError(
                        "Normalisez la rotation et les unités des fichiers du produit."
                    )
                x0, y0, x1, y1 = [float(n) / mm for n in page.trimbox]
                if abs(x1 - x0 - component.width) > 0.1 or abs(y1 - y0 - component.height) > 0.1:
                    raise ValueError(
                        f"{component.name} — {slot.name} : format fini attendu "
                        f"{component.width} × {component.height} mm."
                    )
                bx0, by0, bx1, by1 = [float(n) / mm for n in page.bleedbox]
                mx0, my0, mx1, my1 = [float(n) / mm for n in page.mediabox]
                if (
                    min(x0 - mx0, y0 - my0, mx1 - x1, my1 - y1) < -0.1
                    or min(bx0 - mx0, by0 - my0, mx1 - bx1, my1 - by1) < -0.1
                    or bx1 <= bx0
                    or by1 <= by0
                ):
                    raise ValueError(
                        "Les zones de coupe et de fond perdu doivent rester dans la page."
                    )
                if component.bleed:
                    if min(x0 - bx0, y0 - by0, bx1 - x1, by1 - y1) + 0.1 < component.bleed:
                        raise ValueError(
                            f"{component.name} — {slot.name} : "
                            f"fond perdu de {component.bleed} mm attendu."
                        )
    merged = pikepdf.Pdf.new()
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
        # Artwork can carry larger bleed margins than a technical guide. Normalize
        # each proof copy to the finished format; production originals remain intact.
        proof_sources = []
        labels = []
        for file_index, (file, slot) in enumerate(visuals + masks):
            with open_pdf(file, max_pages=200) as doc:
                for page in doc.pages:
                    page.CropBox = page.trimbox
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
                    page.CropBox = page.trimbox
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
        generate(
            work,
            proof_sources,
            legacy,
            labels=labels,
            combined_guide=guide,
            legend=legend,
            date=date,
        )
        with pikepdf.open(work / "bat.pdf") as doc:
            merged.pages.extend(doc.pages)
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
    merged.save(path)
    merged.close()
    sheet = folder / "fiche-technique.pdf"
    report(
        sheet,
        params.title,
        specs + [("Commentaires", params.notes or "Aucun")],
        "BAT de présentation, couleurs non contractuelles. "
        "Spécifications figées dans les réglages JSON. "
        "Les tracés sont séparés des fichiers de production.",
    )
    return ToolResult(
        tool="burger",
        summary="BAT du produit, fiche technique et fichiers de fabrication prêts.",
        metrics={
            "Fichiers attendus": len(contract),
            "Composants": len(snapshot.variant.components),
            "Pages du BAT": artifact(path, "BAT").pages,
        },
        artifacts=[artifact(path, "BAT A4"), artifact(sheet, "Fiche technique")] + extras,
    )
