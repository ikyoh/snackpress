import json

import pikepdf
import pytest
from PIL import Image, ImageDraw
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
    assert FinishAppearance(mode="path").dash_color == "#ffffff"
    for patch in (
        {"color": "red"},
        {"dash_color": "blue"},
        {"alpha": 1.1},
        {"angle": -1},
        {"mode": "other"},
    ):
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
    finish.appearance.dash_color = "#0000ff"
    result = simulate_finishes(image, [finish], {}, 0, 72)
    assert result.getpixel((50, 20)) == (255, 255, 255)
    assert result.getpixel((2, 0)) == (0, 0, 255)
    assert result.getpixel((7, 0)) == (255, 0, 0)


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
    assert {result.getpixel((49, y)) for y in range(2, 38)} == {
        (255, 0, 0),
        (255, 255, 255),
    }


@pytest.mark.parametrize("dpi", [72, 144])
def test_path_dashes_follow_contours_at_physical_scale(dpi):
    image = Image.new("RGB", (round(80 * dpi / 25.4), round(40 * dpi / 25.4)), "white")
    finish = Finish(
        id="cut",
        name="Découpe",
        appearance={"mode": "path", "color": "#ff0000", "dash_color": "#0000ff"},
    )
    result = simulate_finishes(image, [finish], {}, 0, dpi)
    dash, gap = round(2 * dpi / 25.4), round(dpi / 25.4)
    assert result.getpixel((dash // 2, 0)) == (0, 0, 255)
    assert result.getpixel((dash + gap // 2, 0)) == (255, 0, 0)
    assert result.getpixel((dash + gap + dash // 2, 0)) == (0, 0, 255)
    assert result.getpixel((image.width // 2, image.height // 2)) == (255, 255, 255)


def test_path_dashes_follow_mask_holes_and_separate_shapes(monkeypatch):
    mask = Image.new("RGB", (101, 61), "white")
    draw = ImageDraw.Draw(mask)
    draw.polygon([(4, 4), (50, 4), (50, 50), (35, 50), (35, 40), (4, 40)], fill="black")
    draw.rectangle((15, 15, 30, 25), fill="white")
    draw.ellipse((60, 4, 96, 50), fill="black")
    monkeypatch.setattr(
        "snackpress_tools.finish_appearance.render_page", lambda *args, **kwargs: (mask, None)
    )
    finish = Finish(
        id="cut",
        name="Découpe",
        mask=True,
        appearance={"mode": "path", "color": "#ff0000", "dash_color": "#0000ff"},
    )
    result = simulate_finishes(Image.new("RGB", mask.size, "white"), [finish], {"cut": None}, 0, 72)
    # Both colors follow the outside contour and the inside of the hole.
    assert result.getpixel((6, 4)) == result.getpixel((17, 26)) == (0, 0, 255)
    assert result.getpixel((11, 4)) == result.getpixel((22, 26)) == (255, 0, 0)
    assert result.getpixel((10, 10)) == result.getpixel((20, 20)) == (255, 255, 255)
    curved_colors = {result.getpixel((x, y)) for x in range(60, 97) for y in range(4, 51)}
    assert {(0, 0, 255), (255, 0, 0)} <= curved_colors


@pytest.mark.parametrize("product_id", ["card", "ticket"])
@pytest.mark.parametrize("mode", ["area", "path"])
def test_simulation_in_proof_and_frozen_settings(tmp_path, product_id, mode):
    snapshot = specification(product_id)
    finish = (
        next(f for f in snapshot.finishes if f.id == snapshot.variant.finish_ids[0])
        if snapshot.variant.finish_ids
        else snapshot.finishes[0]
    )
    snapshot.variant.finish_ids = [finish.id]
    # The ticket stock does not accept the seeded varnish: use its own perforation.
    finish.appearance = FinishAppearance(
        mode=mode, gradient=True, alpha=0.6, color="#ff0000", dash_color="#0000ff"
    )
    files = artwork(tmp_path, snapshot)
    original_bytes = [path.read_bytes() for path in files]
    output = tmp_path / "out"
    output.mkdir()
    result = run(output, "burger", files, {"product_snapshot": snapshot.model_dump()})
    assert result.artifacts[0].pages > 0
    text = content(output / "bat.pdf")
    assert text.count("Présentation — visuels avec finitions") == 1
    assert text.count("Contrôle — visuels avec finitions") == 1
    assert "Visuel seul" not in text
    with pikepdf.open(output / "bat.pdf") as pdf:
        for page in list(pdf.pages)[2:]:
            assert_native_guides(page)
        images = [
            next(obj for obj in dict(page.Resources.XObject).values() if obj.Subtype == "/Image")
            for page in [pdf.pages[2], pdf.pages[1]]
        ]
        original, simulation = [pikepdf.PdfImage(image).as_pil_image() for image in images]
        # The displayed bleed remains the original artwork, even for full-area finishes.
        assert original.getpixel((1, original.height // 2)) == simulation.getpixel(
            (1, simulation.height // 2)
        )
    frozen = json.loads((output / "reglages.json").read_text())["settings"]["product_snapshot"]
    saved = next(f for f in frozen["finishes"] if f["id"] == finish.id)
    assert saved["appearance"] == finish.appearance.model_dump()
    assert [path.read_bytes() for path in files] == original_bytes
