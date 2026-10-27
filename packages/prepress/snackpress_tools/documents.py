from contextlib import ExitStack

import numpy as np
import pikepdf
from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from snackpress_imposition.geometry import Settings, calculate
from snackpress_imposition.pdf import compose, inspect

from .catalog import ToolResult
from .common import (
    artifact,
    dimensions,
    load_image,
    new_canvas,
    open_pdf,
    page_selection,
    render_page,
    report,
    write_json,
)


def resource_inventory(page):
    fonts, images, spaces, spots = [], [], set(), set()
    seen = set()
    visited = 0

    def color(value):
        if isinstance(value, pikepdf.Array):
            kind = str(value[0]) if value else ""
            spaces.add(kind)
            if kind == "/Separation" and len(value) > 1:
                spots.add(str(value[1]).lstrip("/"))
            if kind == "/DeviceN" and len(value) > 1:
                spots.update(str(n).lstrip("/") for n in value[1])
            if kind in ("/Indexed", "/ICCBased") and len(value) > 1:
                spaces.add(str(value[1])[:120])
        else:
            spaces.add(str(value))

    def visit(resources, stream, depth=0):
        nonlocal visited
        if depth > 12 or visited > 1000:
            raise ValueError("Structure de ressources trop complexe pour ce prototype.")
        visited += 1
        for name, font in resources.get("/Font", {}).items():
            target = font
            children = font.get("/DescendantFonts", [])
            if children:
                target = children[0]
            descriptor = target.get("/FontDescriptor", {})
            embedded = str(font.get("/Subtype", "")) == "/Type3" or any(
                key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
            )
            fonts.append(
                {
                    "resource": str(name),
                    "name": str(font.get("/BaseFont", "Inconnue")),
                    "type": str(font.get("/Subtype", "Inconnu")),
                    "embedded": embedded,
                }
            )
        for _, cs in resources.get("/ColorSpace", {}).items():
            color(cs)
        try:
            for instruction in pikepdf.parse_content_stream(stream):
                operator = str(instruction.operator)
                if operator in ("k", "K"):
                    spaces.add("/DeviceCMYK")
                elif operator in ("rg", "RG"):
                    spaces.add("/DeviceRGB")
                elif operator in ("g", "G"):
                    spaces.add("/DeviceGray")
        except (pikepdf.PdfError, TypeError, AttributeError):
            spaces.add("Flux partiellement non interprété")
        for name, obj in resources.get("/XObject", {}).items():
            identity = obj.objgen
            if identity != (0, 0):
                if identity in seen:
                    continue
                seen.add(identity)
            subtype = str(obj.get("/Subtype", ""))
            if subtype == "/Image":
                images.append(
                    {
                        "resource": str(name),
                        "width": int(obj.get("/Width", 0)),
                        "height": int(obj.get("/Height", 0)),
                        "bits": int(obj.get("/BitsPerComponent", 0)),
                        "color_space": str(obj.get("/ColorSpace", "Inconnu"))[:120],
                    }
                )
                color(obj.get("/ColorSpace", "Inconnu"))
            elif subtype == "/Form":
                visit(obj.get("/Resources", resources), obj, depth + 1)

    visit(page.resources, page)
    return {
        "fonts": fonts,
        "images": images,
        "color_spaces": sorted(spaces),
        "spots": sorted(spots),
    }


def inventory(path):
    pages = []
    with open_pdf(path) as doc:
        for index, page in enumerate(doc.pages):
            w, h = dimensions(page)
            boxes = {}
            for key in ("MediaBox", "CropBox", "TrimBox", "BleedBox", "ArtBox"):
                if key in page.obj:
                    boxes[key] = [round(float(v) / mm, 4) for v in page.obj[key]]
            pages.append(
                {
                    "page": index + 1,
                    "width_mm": round(w, 3),
                    "height_mm": round(h, 3),
                    "rotation": int(page.obj.get("/Rotate", 0)),
                    "boxes_mm": boxes,
                    "user_unit": float(page.obj.get("/UserUnit", 1)),
                    "annotations": len(page.obj.get("/Annots", [])),
                    **resource_inventory(page),
                }
            )
        return {
            "pages": pages,
            "pdf_version": doc.pdf_version,
            "output_intents": [
                str(x.get("/OutputConditionIdentifier", "Non nommé"))
                for x in doc.Root.get("/OutputIntents", [])
            ],
            "has_forms": "/AcroForm" in doc.Root,
        }


def chili(folder, files, p):
    data = inventory(files[0])
    rows = [
        ("Version PDF", data["pdf_version"]),
        ("Pages", len(data["pages"])),
        ("OutputIntents déclarés", ", ".join(data["output_intents"]) or "Aucun"),
    ]
    for page in data["pages"]:
        rows += [
            (
                f"Page {page['page']}",
                f"{page['width_mm']} × {page['height_mm']} mm ; "
                f"rotation {page['rotation']}° ; UserUnit {page['user_unit']}",
            ),
            ("Boîtes déclarées (mm)", str(page["boxes_mm"])),
            (
                "Polices",
                "; ".join(
                    f"{f['name']} "
                    f"({'intégrée' if f['embedded'] else 'non intégrée / non déclarée'})"
                    for f in page["fonts"]
                )
                or "Aucune déclarée",
            ),
            (
                "Images déclarées",
                "; ".join(
                    f"{i['width']} × {i['height']} px, {i['bits']} bits" for i in page["images"]
                )
                or "Aucune déclarée",
            ),
            ("Espaces couleur", ", ".join(page["color_spaces"])),
            ("Tons directs", ", ".join(page["spots"]) or "Aucun déclaré"),
        ]
    path, raw = folder / "inspection.pdf", folder / "inspection.json"
    report(
        path,
        "Chili Dog — inspection structurelle",
        rows,
        (
            "Ressources et boîtes déclarées. La résolution effective, la "
            "conformité prépresse et PDF/X ne sont pas certifiées. Les images "
            "inline et les ressources non référencées peuvent ne pas être "
            "inventoriées."
        ),
        branded_header=True,
    )
    write_json(raw, data)
    return ToolResult(
        tool="chili-dog",
        summary=f"{len(data['pages'])} page(s) inspectée(s).",
        metrics={
            "Pages": len(data["pages"]),
            "Images déclarées": sum(len(x["images"]) for x in data["pages"]),
        },
        artifacts=[
            artifact(path, "Rapport d’inspection"),
            artifact(raw, "Données structurelles JSON"),
        ],
    )


def donut(folder, files, p):
    source = files[0]
    if source.suffix == ".pdf":
        with open_pdf(source, 20) as doc:
            count = len(doc.pages)
    else:
        count = 1
    if p.output == "png" and count != 1:
        raise ValueError(
            "La sortie PNG exige une seule page. Choisissez PDF pour toutes les pages."
        )
    path = folder / ("fond-perdu.pdf" if p.output == "pdf" else "fond-perdu.png")
    c = new_canvas(path, 100, 100) if p.output == "pdf" else None
    sizes = []
    for index in range(count):
        if source.suffix == ".pdf":
            img, (w, h) = render_page(source, index, p.dpi)
        else:
            img = load_image(source)
            w, h = p.image_width, p.image_width * img.height / img.width
            # Respect requested output resolution for image inputs as well.
            target = (max(1, round(w / 25.4 * p.dpi)), max(1, round(h / 25.4 * p.dpi)))
            if target[0] * target[1] > 20_000_000:
                raise ValueError(
                    "Image de sortie trop grande. Réduisez la résolution ou la largeur."
                )
            img = img.resize(target, Image.Resampling.LANCZOS)
        bx, by = max(1, round(p.bleed / w * img.width)), max(1, round(p.bleed / h * img.height))
        if (img.width + 2 * bx) * (img.height + 2 * by) > 20_000_000:
            raise ValueError("Sortie raster trop grande. Réduisez la résolution ou le fond perdu.")
        padded = Image.fromarray(
            np.pad(
                np.asarray(img),
                ((by, by), (bx, bx), (0, 0)),
                mode="symmetric" if p.method == "mirror" else "edge",
            )
        )
        if c:
            c.setPageSize(((w + 2 * p.bleed) * mm, (h + 2 * p.bleed) * mm))
            c.drawImage(
                ImageReader(padded),
                0,
                0,
                width=(w + 2 * p.bleed) * mm,
                height=(h + 2 * p.bleed) * mm,
            )
            c.showPage()
        else:
            padded.save(path, dpi=(p.dpi, p.dpi))
        sizes.append((w, h))
    if c:
        c.save()
        with pikepdf.open(path, allow_overwriting_input=True) as doc:
            for page, (w, h) in zip(doc.pages, sizes, strict=True):
                page.TrimBox = pikepdf.Array(
                    [p.bleed * mm, p.bleed * mm, (p.bleed + w) * mm, (p.bleed + h) * mm]
                )
                page.BleedBox = page.MediaBox
            doc.save(path)
    return ToolResult(
        tool="donut",
        summary=f"{p.bleed:g} mm ajoutés sur les 4 bords de {count} page(s).",
        metrics={"Pages": count, "Résolution (dpi)": p.dpi},
        warnings=[
            (
                "La zone visible source devient le format fini ; les anciennes "
                "boîtes de coupe ne sont pas utilisées."
            ),
            (
                "Sortie RGB rasterisée : chaque bord, les petits textes et les "
                "couleurs doivent être relus."
            ),
        ],
        artifacts=[artifact(path, "Document avec fond perdu")],
    )


def tiramisu(folder, files, p):
    counts = []
    for source in files:
        with open_pdf(source) as doc:
            counts.append(len(doc.pages))
    overlay_path, diff_path = folder / "superposition.pdf", folder / "differences.pdf"
    overlay = new_canvas(overlay_path, 210, 297)
    diff = new_canvas(diff_path, 210, 297)
    pages = []
    for index in range(max(counts)):
        rendered = [
            render_page(f, index, p.dpi, max_pixels=8_000_000) if index < n else None
            for f, n in zip(files, counts, strict=True)
        ]
        width = max(r[0].width for r in rendered if r)
        height = max(r[0].height for r in rendered if r)
        if width * height > 20_000_000:
            raise ValueError("Dimensions de comparaison trop grandes. Réduisez la résolution.")
        images = []
        extents = []
        for r in rendered:
            image = Image.new("RGB", (width, height), "white")
            mask = np.zeros((height, width), dtype=bool)
            if r:
                image.paste(r[0], (0, 0))
                mask[: r[0].height, : r[0].width] = True
            images.append(image)
            extents.append(mask)
        delta = np.max(
            np.abs(np.asarray(images[0]).astype(np.int16) - np.asarray(images[1]).astype(np.int16)),
            axis=2,
        )
        changed = (delta > p.tolerance) | (extents[0] != extents[1])
        rate = float(changed.mean() * 100)
        heat = np.asarray(images[0].convert("L").convert("RGB")).copy()
        heat[:] = 220 + heat // 8
        heat[changed] = [211, 66, 49]
        wmm, hmm = width / p.dpi * 25.4, height / p.dpi * 25.4
        for c, image in (
            (overlay, Image.blend(images[0], images[1], p.opacity)),
            (diff, Image.fromarray(heat)),
        ):
            c.setPageSize((wmm * mm, hmm * mm))
            c.drawImage(ImageReader(image), 0, 0, width=wmm * mm, height=hmm * mm)
            c.showPage()
        pages.append(
            {
                "page": index + 1,
                "difference_percent": round(rate, 4),
                "first_present": index < counts[0],
                "second_present": index < counts[1],
                "dimensions_differ": rendered[0] is None
                or rendered[1] is None
                or rendered[0][0].size != rendered[1][0].size,
            }
        )
    overlay.save()
    diff.save()
    raw, summary = folder / "comparaison.json", folder / "rapport-comparaison.pdf"
    write_json(raw, {"dpi": p.dpi, "tolerance": p.tolerance, "pages": pages})
    report(
        summary,
        "Tiramisu — comparaison visuelle",
        [
            (
                f"Page {x['page']}",
                f"{x['difference_percent']:.3f} % de pixels différents"
                + (" ; dimensions ou présence différentes" if x["dimensions_differ"] else ""),
            )
            for x in pages
        ],
        (
            "Raster RGB, page par page, alignement au coin supérieur gauche. "
            "Rouge = différence supérieure à la tolérance. Aucun recalage "
            "automatique ni comparaison sémantique."
        ),
    )
    return ToolResult(
        tool="tiramisu",
        summary=f"{len(pages)} page(s) comparée(s).",
        metrics={
            "Pages comparées": len(pages),
            "Pages différentes": sum(x["difference_percent"] > 0 for x in pages),
        },
        artifacts=[
            artifact(overlay_path, "Superposition"),
            artifact(diff_path, "Carte des différences"),
            artifact(summary, "Rapport par page"),
            artifact(raw, "Mesures JSON"),
        ],
    )


def poke(folder, files, p):
    data = inventory(files[0])
    rows, estimates = [], []
    for index, page in enumerate(data["pages"]):
        image, _ = render_page(files[0], index, p.dpi, max_pixels=4_000_000)
        rgb = np.asarray(image, dtype=np.float32) / 255
        k = 1 - rgb.max(axis=2)
        denominator = np.maximum(1 - k, 1e-6)
        cmy = (1 - rgb - k[:, :, None]) / denominator[:, :, None]
        cmy = np.clip(cmy, 0, 1)
        means = [float(cmy[:, :, i].mean() * 100) for i in range(3)] + [float(k.mean() * 100)]
        total = cmy.sum(axis=2) + k
        estimate = {
            "page": index + 1,
            "mean_cmyk_percent": [round(v, 3) for v in means],
            "max_sum_estimate_percent": round(float(total.max() * 100), 2),
            "color_spaces": page["color_spaces"],
            "spots": page["spots"],
        }
        estimates.append(estimate)
        rows.extend(
            [
                (f"Page {index + 1}", ", ".join(page["color_spaces"]) or "Non déclaré"),
                ("Tons directs déclarés", ", ".join(page["spots"]) or "Aucun"),
                ("Moyennes écran C / M / J / N", " / ".join(f"{x:.2f} %" for x in means)),
                (
                    "Somme maximale estimée",
                    f"{estimate['max_sum_estimate_percent']} % (non certifiée)",
                ),
            ]
        )
    path, raw = folder / "couleurs.pdf", folder / "couleurs.json"
    report(
        path,
        "Poké — couleurs et estimation écran",
        rows,
        (
            "Estimation CMJN issue du rendu RGB avec retrait du noir K = 1 - "
            "max(R,G,B). Sans profil de séparation ni simulation RIP. Ce "
            "calcul ne mesure ni les plaques, ni le TAC réel, ni la "
            "consommation d’encre."
        ),
        branded_header=True,
    )
    write_json(
        raw, {"method": "RGB screen estimate; K=1-max(R,G,B)", "dpi": p.dpi, "pages": estimates}
    )
    return ToolResult(
        tool="poke",
        summary=f"Espaces couleur et estimation écran de {len(estimates)} page(s).",
        metrics={
            "Pages": len(estimates),
            "Tons directs déclarés": len({s for x in estimates for s in x["spots"]}),
        },
        artifacts=[artifact(path, "Rapport couleur"), artifact(raw, "Données couleur JSON")],
    )


def booklet_order(count):
    return [[count - 1 - 2 * i, 2 * i, 2 * i + 1, count - 2 - 2 * i] for i in range(count // 4)]


def layer(folder, files, p):
    path, sheet = folder / "imposition.pdf", folder / "fiche-imposition.pdf"
    if p.mode == "repeat":
        info = inspect(files[0])
        s = Settings(
            sheet_width=p.sheet_width,
            sheet_height=p.sheet_height,
            margin=p.margin,
            gap=p.gap,
            quantity=p.quantity,
            flip=p.flip,
            trim_width=info.pages[0].width,
            trim_height=info.pages[0].height,
            confirm_trim=True,
        )
        plan = calculate(s, len(info.pages) == 2)
        compose(files[0], path, plan)
        report(
            sheet,
            "Layer Cake — répétition",
            [
                ("Poses par feuille", plan.poses),
                ("Grille", f"{plan.columns} colonnes × {plan.rows} lignes ; {plan.rotation}°"),
                ("Répétitions de la feuille / paire type", plan.sheets),
                ("Exemplaires produits", plan.produced),
                ("Retournement", p.flip),
            ],
            (
                "Imprimer à 100 %. Format fini pris dans la TrimBox, ou format "
                "visible si absente. Vérifier le retournement et les repères sur "
                "presse."
            ),
        )
        metrics = {
            "Poses": plan.poses,
            "Feuilles à tirer": plan.sheets,
            "Exemplaires": plan.produced,
        }
        warnings = plan.warnings
    else:
        with open_pdf(files[0]) as source:
            count = len(source.pages)
            if count < 4 or count % 4:
                raise ValueError(
                    (
                        "Le livret doit contenir de 4 à 80 pages, en multiple de 4. "
                        "Ajoutez les pages blanches dans le PDF source."
                    )
                )
            if p.sheet_width <= 4 * p.margin or p.sheet_height <= 2 * p.margin:
                raise ValueError(
                    "Les marges ne laissent pas assez de place aux deux pages du livret."
                )
            out = pikepdf.Pdf.new()
            order = booklet_order(count)
            pairs = []
            half = p.sheet_width / 2
            for group in order:
                for a, b in (group[:2], group[2:]):
                    page = out.add_blank_page(page_size=(p.sheet_width * mm, p.sheet_height * mm))
                    for index, left in ((a, 0), (b, half)):
                        rect = pikepdf.Rectangle(
                            (left + p.margin) * mm,
                            p.margin * mm,
                            (left + half - p.margin) * mm,
                            (p.sheet_height - p.margin) * mm,
                        )
                        page.add_overlay(source.pages[index], rect)
                    pairs.append((a + 1, b + 1))
            out.save(path)
        physical = count // 4
        report(
            sheet,
            "Layer Cake — livret piqué",
            [
                ("Pages source", count),
                ("Feuilles physiques par livret", physical),
                ("Livrets demandés", p.quantity),
                ("Total feuilles à tirer", physical * p.quantity),
                *[
                    (
                        f"Feuille {i // 2 + 1} / {'recto' if i % 2 == 0 else 'verso'}",
                        f"Gauche : page {a} ; droite : page {b}",
                    )
                    for i, (a, b) in enumerate(pairs)
                ],
            ],
            (
                "Pages source ajustées proportionnellement aux demi-feuilles. "
                "Ordre extérieur vers intérieur, lecture gauche à droite. Imprimer"
                " toutes les faces une fois par livret, sans réimposition du "
                "pilote. Aucune compensation de chasse. Valider l’épreuve et le "
                "retournement sur presse."
            ),
        )
        metrics = {
            "Pages du livret": count,
            "Feuilles par livret": physical,
            "Feuilles à tirer": physical * p.quantity,
        }
        warnings = [
            "Ajustement proportionnel des pages : contrôler les dimensions finales.",
            "Aucune compensation de chasse ; épreuve de pliage et de retournement requise.",
        ]
    return ToolResult(
        tool="layer-cake",
        summary="Imposition et fiche de tirage prêtes.",
        metrics=metrics,
        warnings=warnings,
        artifacts=[artifact(path, "PDF imposé"), artifact(sheet, "Fiche de tirage")],
    )


def bento(folder, files, p):
    if p.operation != "merge" and len(files) != 1:
        raise ValueError("Pour extraire, réordonner ou pivoter, importez un seul PDF.")
    with ExitStack() as stack:
        docs = [stack.enter_context(open_pdf(f)) for f in files]
        out = pikepdf.Pdf.new()
        if p.operation == "merge":
            for doc in docs:
                out.pages.extend(doc.pages)
        else:
            selected = page_selection(p.pages, len(docs[0].pages))
            if p.operation == "reorder" and (
                len(selected) != len(docs[0].pages) or len(set(selected)) != len(selected)
            ):
                raise ValueError("Le réordre doit contenir chaque page une seule fois.")
            if p.operation in ("extract", "reorder"):
                for i in selected:
                    out.pages.append(docs[0].pages[i])
            else:
                out.pages.extend(docs[0].pages)
                for i in set(selected):
                    out.pages[i].rotate(p.rotation, relative=True)
        if len(out.pages) > 200:
            raise ValueError("La sortie est limitée à 200 pages.")
        for page in out.pages:
            for key in ("/Annots", "/AA"):
                if key in page.obj:
                    del page.obj[key]
        path = folder / "assemblage.pdf"
        out.save(path)
        count = len(out.pages)
    return ToolResult(
        tool="bento",
        summary=f"Document de {count} page(s) prêt.",
        metrics={"Pages en sortie": count, "Fichiers source": len(files)},
        warnings=[
            (
                "Signatures numériques, formulaires, annotations et métadonnées de"
                " document non conservés."
            )
        ],
        artifacts=[artifact(path, "PDF assemblé")],
    )
