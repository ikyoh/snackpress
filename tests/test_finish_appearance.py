import json

import pikepdf
import pytest
from PIL import Image
from pydantic import ValidationError
from reportlab.lib.units import mm
from snackpress_tools.common import new_canvas
from snackpress_tools.finish_appearance import simulate_finishes
from snackpress_tools.products import Finish, FinishAppearance
from snackpress_tools.runner import run
from test_burger import assert_native_guides
from test_products import artwork, content, specification


def test_old_finishes_and_invalid_appearance():
    assert Finish(id="old", name="Ancienne finition").appearance.mode == "none"
    for patch in ({"color": "red"}, {"alpha": 1.1}, {"angle": -1}, {"mode": "other"}):
        with pytest.raises(ValidationError):
            FinishAppearance(**patch)


def test_area_opacity_gradient_and_path():
    image = Image.new("RGB", (101, 41), "white")
    finish = Finish(
        id="foil",
        name="Dorure",
        appearance={
            "mode": "area",
            "color": "#ff0000",
            "alpha": 0.5,
        },
    )
    result = simulate_finishes(image, [finish], {}, 0, 72)
    assert result.getpixel((50, 20)) == (255, 127, 127)
    finish.appearance.alpha = 0
    assert simulate_finishes(image, [finish], {}, 0, 72).tobytes() == image.tobytes()
    finish.appearance.alpha = 1
    finish.appearance.gradient = True
    finish.appearance.end_color = "#0000ff"
    result = simulate_finishes(image, [finish], {}, 0, 72)
    assert result.getpixel((0, 20)) == (255, 0, 0)
    assert result.getpixel((100, 20)) == (0, 0, 255)
    finish.appearance.angle = 90
    result = simulate_finishes(image, [finish], {}, 0, 72)
    assert result.getpixel((50, 40)) == (255, 0, 0)
    assert result.getpixel((50, 0)) == (0, 0, 255)
    finish.appearance.mode = "path"
    result = simulate_finishes(image, [finish], {}, 0, 72)
    assert result.getpixel((50, 20)) == (255, 255, 255)
    assert result.getpixel((0, 20)) == (255, 0, 0)


def test_mask_coverage_and_page_order(tmp_path):
    path = tmp_path / "mask.pdf"
    c = new_canvas(path, 100 / mm, 40 / mm)
    c.rect(0, 0, 50, 40, fill=1, stroke=0)
    c.showPage()
    c.rect(50, 0, 50, 40, fill=1, stroke=0)
    c.save()
    image = Image.new("RGB", (100, 40), "white")
    finish = Finish(
        id="foil",
        name="Dorure",
        mask=True,
        appearance={
            "mode": "area",
            "color": "#ff0000",
            "alpha": 1,
        },
    )
    front = simulate_finishes(image, [finish], {"foil": path}, 0, 72)
    back = simulate_finishes(image, [finish], {"foil": path}, 1, 72)
    assert front.getpixel((25, 20)) == back.getpixel((75, 20)) == (255, 0, 0)
    assert front.getpixel((75, 20)) == back.getpixel((25, 20)) == (255, 255, 255)
    finish.appearance.mode = "path"
    result = simulate_finishes(image, [finish], {"foil": path}, 0, 72)
    assert result.getpixel((25, 20)) == (255, 255, 255)
    assert result.getpixel((49, 20)) == (255, 0, 0)


@pytest.mark.parametrize("product_id", ["card", "ticket"])
def test_simulation_in_proof_and_frozen_settings(tmp_path, product_id):
    snapshot = specification(product_id)
    finish = (
        next(f for f in snapshot.finishes if f.id == snapshot.variant.finish_ids[0])
        if snapshot.variant.finish_ids
        else snapshot.finishes[0]
    )
    snapshot.variant.finish_ids = [finish.id]
    # The ticket stock does not accept the seeded varnish: use its own perforation.
    finish.appearance = FinishAppearance(mode="area", gradient=True, alpha=0.6)
    files = artwork(tmp_path, snapshot)
    original_bytes = [path.read_bytes() for path in files]
    output = tmp_path / "out"
    output.mkdir()
    result = run(output, "burger", files, {"product_snapshot": snapshot.model_dump()})
    assert result.artifacts[0].pages > 0
    text = content(output / "bat.pdf")
    assert text.count("Simulation des finitions") == 2
    assert "Visuel seul" not in text
    with pikepdf.open(output / "bat.pdf") as pdf:
        for page in pdf.pages:
            assert_native_guides(page)
    frozen = json.loads((output / "reglages.json").read_text())["settings"]["product_snapshot"]
    saved = next(f for f in frozen["finishes"] if f["id"] == finish.id)
    assert saved["appearance"] == finish.appearance.model_dump()
    assert [path.read_bytes() for path in files] == original_bytes
