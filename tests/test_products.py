import json

import pikepdf
import pypdfium2 as pdfium
import pytest
from pydantic import ValidationError
from reportlab.lib.units import mm
from snackpress_tools.catalog import Burger
from snackpress_tools.common import new_canvas
from snackpress_tools.preview import render
from snackpress_tools.products import Guide, PrintCatalog, Snapshot, seed_catalog, snapshot_slots
from snackpress_tools.runner import run


def specification(product_id="card"):
    catalog = seed_catalog()
    product = next(p for p in catalog.products if p.id == product_id)
    return Snapshot(
        product_name=product.name,
        category_name="Tests",
        variant=product.variants[0],
        materials=catalog.materials,
        finishes=catalog.finishes,
    )


def artwork(folder, snapshot):
    files = []
    for i, (component, slot) in enumerate(snapshot_slots(snapshot)):
        path = folder / f"source-{i}.pdf"
        bleed = component.bleed
        c = new_canvas(path, component.width + 2 * bleed, component.height + 2 * bleed)
        for page in range(slot.pages):
            c.setFillColorRGB(0.8, 0.3, 0.5)
            c.rect(
                0,
                0,
                (component.width + 2 * bleed) * mm,
                (component.height + 2 * bleed) * mm,
                fill=1,
            )
            c.setFont("Snack", 12)
            c.drawString((bleed + 10) * mm, (bleed + 15) * mm, f"Visuel {page + 1}")
            c.showPage()
        c.save()
        with pikepdf.open(path, allow_overwriting_input=True) as doc:
            for page in doc.pages:
                page.TrimBox = pikepdf.Array(
                    [
                        bleed * mm,
                        bleed * mm,
                        (bleed + component.width) * mm,
                        (bleed + component.height) * mm,
                    ]
                )
                page.BleedBox = page.MediaBox
            doc.save(path)
        files.append(path)
    return files


def content(path):
    with pdfium.PdfDocument(str(path)) as pdf:
        return "\n".join(page.get_textpage().get_text_range() for page in pdf)


@pytest.mark.parametrize("product_id", ["card", "leaflet", "brochure", "banner", "label", "ticket"])
def test_seed_products_generate_proofs_and_public_artifacts(tmp_path, product_id):
    snapshot = specification(product_id)
    files = artwork(tmp_path, snapshot)
    output = tmp_path / "result"
    output.mkdir()
    result = run(output, "burger", files, {"product_snapshot": snapshot.model_dump()})
    assert result.metrics["Composants"] == len(snapshot.variant.components)
    assert result.artifacts[0].pages > 0
    for item in result.artifacts:
        assert (output / item.name).is_file(), item.name
    frozen = json.loads((output / "reglages.json").read_text())["settings"]["product_snapshot"]
    assert frozen["product_name"] == snapshot.product_name
    with pdfium.PdfDocument(str(output / "bat.pdf")) as pdf:
        for index, page in enumerate(pdf, 1):
            text = page.get_textpage().get_text_range()
            assert "Date du BAT :" in text and "snackpress.app" in text
            assert f"Page {index} / {len(pdf)}" in text
    if product_id == "ticket":
        series = next(item for item in result.artifacts if "serie-billets" in item.name)
        assert series.pages == 50
        text = content(output / series.name)
        assert text.count("0001") == 2 and text.count("0050") == 2
        assert result.metrics["Pages du BAT"] == 5


def test_sushi_component_uses_product_bleed_and_exports_both_line_types(tmp_path):
    snapshot = specification("label").model_dump()
    component = snapshot["variant"]["components"][0]
    component["bleed"] = 4
    component["guides"][0]["settings"] = {
        "shape": "none",
        "bleed": 0,
        "lines": [
            {"kind": "cut", "axis": "horizontal", "position": 10},
            {"kind": "crease", "axis": "vertical", "position": 25},
        ],
    }
    snapshot = Snapshot.model_validate(snapshot)
    assert snapshot.variant.components[0].guides[0].settings["bleed"] == 4
    files = artwork(tmp_path, snapshot)
    output = tmp_path / "out"
    output.mkdir()
    result = run(output, "burger", files, {"product_snapshot": snapshot.model_dump()})
    guide = next(a for a in result.artifacts if "traces" in a.name)
    with pikepdf.open(output / guide.name) as pdf:
        assert [float(v) / mm for v in pdf.pages[0].TrimBox] == pytest.approx([4, 4, 89, 59])
    text = content(output / "bat.pdf")
    assert "Découpe (CutContour)" in text and "Rainage (Crease)" in text


def test_multiple_guides_share_trim_origin(tmp_path):
    snapshot = specification("leaflet")
    component = snapshot.variant.components[0]
    component.guides.append(Guide(tool="pizza"))
    snapshot = Snapshot.model_validate(snapshot.model_dump())
    files = artwork(tmp_path, snapshot)
    output = tmp_path / "out"
    output.mkdir()
    result = run(output, "burger", files, {"product_snapshot": snapshot.model_dump()})
    with pdfium.PdfDocument(str(output / "bat.pdf")) as pdf:
        marked_text = pdf[1].get_textpage().get_text_range()
        assert "Légende des repères" in marked_text
        assert "Zone de sécurité" in marked_text and "Pliage" in marked_text
    guide = next(a for a in result.artifacts if "traces" in a.name)
    with pikepdf.open(output / guide.name) as doc:
        assert len(doc.pages) == 2
        trim = doc.pages[0].trimbox
        assert float(trim[0]) / mm == pytest.approx(15)
        assert float(trim[2] - trim[0]) / mm == pytest.approx(297)
        assert len(doc.pages[0].Resources.XObject) == 2
    with pikepdf.open(output / "bat.pdf") as doc:
        marked = doc.pages[2]
        images = [obj for obj in dict(marked.Resources.XObject).values() if obj.Subtype == "/Image"]
        forms = [obj for obj in dict(marked.Resources.XObject).values() if obj.Subtype == "/Form"]
        assert not images
        forms = [form for form in forms if form.get("/SnackpressRole") == "/Guide"]
        assert len(forms) == 1
        # The combined Pizza/Taco template keeps both of its native PDF layers.
        layers = list(dict(forms[0].Resources.XObject).values())
        assert len(layers) == 2
        assert all(layer.Subtype == "/Form" for layer in layers)
        # The combined guide must also carry the mirrored Taco layer on the verso.
        verso = doc.pages[3]
        combined = next(
            obj
            for obj in dict(verso.Resources.XObject).values()
            if obj.get("/SnackpressRole") == "/Guide"
        )
        positions = [
            [
                float(args[0]) / mm - 15
                for args, op in pikepdf.parse_content_stream(layer)
                if str(op) == "m" and len(args) == 2 and abs(float(args[1]) / mm - 15) < 0.01
            ]
            for layer in dict(combined.Resources.XObject).values()
        ]
        assert any(values == pytest.approx([97, 196]) for values in positions)


def test_product_accepts_complete_bleed_format_without_trimbox(tmp_path):
    snapshot = specification("banner")
    component = snapshot.variant.components[0]
    component.width, component.height, component.bleed = 800, 2000, 3
    component.guides = [Guide(tool="pizza")]
    files = artwork(tmp_path, snapshot)
    for file in files:
        with pikepdf.open(file, allow_overwriting_input=True) as pdf:
            for page in pdf.pages:
                del page.TrimBox
            pdf.save(file)
    originals = [file.read_bytes() for file in files]
    out = tmp_path / "out"
    out.mkdir()
    result = run(out, "burger", files, {"product_snapshot": snapshot.model_dump()})
    assert result.metrics["Composants"] == 1
    with pikepdf.open(out / "sources-validees/source-0.pdf") as pdf:
        assert [float(n) / mm for n in pdf.pages[0].trimbox] == pytest.approx([3, 3, 803, 2003])
    assert [file.read_bytes() for file in files] == originals


def test_finish_masks_and_compatibility_rules(tmp_path):
    snapshot = specification()
    snapshot.variant.finish_ids = ["varnish", "lamination"]
    assert len(snapshot_slots(snapshot)) == 3
    output = tmp_path / "out"
    output.mkdir()
    run(output, "burger", artwork(tmp_path, snapshot), {"product_snapshot": snapshot.model_dump()})
    snapshot.variant.components[0].material_id = "offset"
    with pytest.raises(ValidationError, match="incompatible"):
        Burger(product_snapshot=snapshot.model_dump())
    snapshot = specification()
    snapshot.finishes[0].excludes = ["lamination"]
    snapshot.variant.finish_ids = ["varnish", "lamination"]
    with pytest.raises(ValidationError, match="incompatibles"):
        Snapshot.model_validate(snapshot.model_dump())


def test_wrong_file_count_dimensions_pages_and_bleed_rejected(tmp_path):
    snapshot = specification()
    files = artwork(tmp_path, snapshot)
    for patch, match in [
        ({"files": files[:1]}, "2 fichier"),
        ({"width": 90}, "format fini"),
        ({"pages": 2}, "page"),
        ({"bleed": 5}, "fond perdu"),
    ]:
        copy = snapshot.model_copy(deep=True)
        comp = copy.variant.components[0]
        if "width" in patch:
            comp.width = patch["width"]
        if "pages" in patch:
            comp.slots[0].pages = patch["pages"]
        if "bleed" in patch:
            comp.bleed = patch["bleed"]
        output = tmp_path / f"out-{match}"
        output.mkdir()
        with pytest.raises(ValueError, match=match):
            run(
                output, "burger", patch.get("files", files), {"product_snapshot": copy.model_dump()}
            )


def test_ticket_suffix_offsets_duplex_booklets_and_preview(tmp_path):
    snapshot = specification("ticket")
    component = snapshot.variant.components[0]
    component.slots.append(component.slots[0].model_copy(update={"id": "back", "name": "Verso"}))
    tickets = component.tickets
    tickets.prefix = "T-"
    tickets.suffix = "-A"
    tickets.count = 3
    tickets.binding = "stapled"
    tickets.per_book = 2
    tickets.placements[1].offset = 100
    tickets.placements[1].face = 2
    tickets.code = "qr"
    files = artwork(tmp_path, snapshot)
    settings = {"product_snapshot": snapshot.model_dump()}
    for preview in (False, True):
        output = tmp_path / str(preview)
        output.mkdir()
        result = (
            render(output, "burger", files, settings)
            if preview
            else run(output, "burger", files, settings)
        )
        series = next(a for a in result.artifacts if "billets.pdf" in a.name)
        assert series.pages == (4 if preview else 6)
        text = content(output / series.name)
        assert "T-0001-A" in text and "T-0103-A" in text
        assert ("T-0002-A" in text) is not preview
        manifest = next(a for a in result.artifacts if "carnets.pdf" in a.name)
        assert "Carnet 2" in content(output / manifest.name)
    assert settings["product_snapshot"]["variant"]["components"][0]["tickets"]["count"] == 3


def test_catalog_references_and_geometry():
    catalog = seed_catalog().model_dump()
    catalog["categories"][0]["parent_id"] = catalog["categories"][0]["id"]
    with pytest.raises(ValidationError, match="Hiérarchie"):
        PrintCatalog.model_validate(catalog)
    snapshot = specification("ticket").model_dump()
    snapshot["variant"]["components"][0]["guides"][0]["settings"]["positions"] = [999]
    with pytest.raises(ValidationError, match="perforations"):
        Snapshot.model_validate(snapshot)
    snapshot = specification("label").model_dump()
    snapshot["variant"]["components"][0]["guides"].append({"tool": "pizza"})
    with pytest.raises(ValidationError, match="référence"):
        Snapshot.model_validate(snapshot)


def test_pagination_and_snapshot_resource_limits():
    snapshot = specification("brochure").model_dump()
    snapshot["variant"]["components"][1]["slots"][0]["pages"] = 7
    with pytest.raises(ValidationError, match="multiple de 4"):
        Snapshot.model_validate(snapshot)
    snapshot = specification().model_dump()
    snapshot["variant"]["finish_ids"] = ["varnish"]
    snapshot["variant"]["components"][0]["slots"][0]["pages"] = 100
    snapshot["variant"]["components"][0]["slots"][1]["pages"] = 1
    with pytest.raises(ValidationError, match="200 pages"):
        Snapshot.model_validate(snapshot)


def test_missing_product_does_not_fall_back_to_classic():
    with pytest.raises(ValidationError, match="Choisissez un produit"):
        Burger(source_mode="catalog")
    assert Burger().source_mode == "classic"


def test_product_pizza_template_dimensions_and_frozen_proof(tmp_path):
    snapshot = specification().model_dump()
    component = snapshot["variant"]["components"][0]
    component["pizza_template"] = {"id": "pizza-config", "name": "Carte atelier", "revision": 1}
    component["guides"] = [
        {
            "tool": "pizza",
            "settings": {
                "width": component["width"],
                "height": component["height"],
                "bleed": component["bleed"],
            },
        }
    ]
    valid = Snapshot.model_validate(snapshot)
    assert valid.variant.components[0].pizza_template.name == "Carte atelier"
    component["width"] += 10
    with pytest.raises(ValueError, match="fixée par le gabarit"):
        Snapshot.model_validate(snapshot)
    settings = component["guides"][0]["settings"]
    settings.update(width_mode="bounded", width_min=80, width_max=120)
    valid = Snapshot.model_validate(snapshot)
    component["width"] = 130
    with pytest.raises(ValueError, match="comprise entre"):
        Snapshot.model_validate(snapshot)
    component["width"] = 100
    component["bleed"] += 1
    with pytest.raises(ValueError, match="fond perdu est fixé"):
        Snapshot.model_validate(snapshot)
    component["bleed"] -= 1
    component["guides"] = []
    with pytest.raises(ValueError, match="conservé dans les tracés"):
        Snapshot.model_validate(snapshot)
    files = artwork(tmp_path, valid)
    output = tmp_path / "proof"
    output.mkdir()
    result = run(output, "burger", files, {"product_snapshot": valid.model_dump()})
    assert result.artifacts
    frozen = json.loads((output / "reglages.json").read_text())["settings"]["product_snapshot"]
    assert frozen["variant"]["components"][0]["pizza_template"]["name"] == "Carte atelier"
    assert frozen["variant"]["components"][0]["width"] == valid.variant.components[0].width
