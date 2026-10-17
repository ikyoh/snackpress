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
    if product_id == "ticket":
        series = next(item for item in result.artifacts if "serie-billets" in item.name)
        assert series.pages == 50
        text = content(output / series.name)
        assert text.count("0001") == 2 and text.count("0050") == 2
        assert result.metrics["Pages du BAT"] == 4


def test_multiple_guides_share_trim_origin(tmp_path):
    snapshot = specification("leaflet")
    component = snapshot.variant.components[0]
    component.guides.append(Guide(tool="pizza"))
    snapshot = Snapshot.model_validate(snapshot.model_dump())
    files = artwork(tmp_path, snapshot)
    output = tmp_path / "out"
    output.mkdir()
    result = run(output, "burger", files, {"product_snapshot": snapshot.model_dump()})
    guide = next(a for a in result.artifacts if "traces" in a.name)
    with pikepdf.open(output / guide.name) as doc:
        trim = doc.pages[0].trimbox
        assert float(trim[0]) / mm == pytest.approx(15)
        assert float(trim[2] - trim[0]) / mm == pytest.approx(297)
        assert len(doc.pages[0].Resources.XObject) == 2


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
