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


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_five_gradient_steps_and_segment_interpolation(angle):
    finish = Finish(
        id="foil",
        name="Dorure",
        appearance={
            "mode": "area",
            "gradient": True,
            "alpha": 1,
            "angle": angle,
            "color": "#ff0000",
            "end_color": "#ffffff",
            "gradient_stops": [
                {"color": "#00ff00", "position": 10},
                {"color": "#0000ff", "position": 40},
                {"color": "#000000", "position": 90},
            ],
        },
    )
    result = simulate_finishes(Image.new("RGB", (101, 101), "white"), [finish], {}, 0, 72)

    def pixel(position):
        x, y = {
            0: (position, 50),
            90: (50, 100 - position),
            180: (100 - position, 50),
            270: (50, position),
        }[angle]
        return result.getpixel((x, y))

    assert pixel(0) == (255, 0, 0)
    assert pixel(10) == (0, 255, 0)
    assert pixel(40) == (0, 0, 255)
    assert pixel(90) == (0, 0, 0)
    assert pixel(100) == (255, 255, 255)
    # Floating-point projection and 8-bit rounding can differ by one channel level.
    assert pixel(5) == pytest.approx((128, 128, 0), abs=1)
    assert pixel(25) == pytest.approx((0, 128, 128), abs=1)
    assert pixel(65) == pytest.approx((0, 0, 128), abs=1)


def test_five_step_gradient_is_clipped_to_mask_and_finished_region(monkeypatch):
    image = Image.new("RGB", (107, 107), "blue")
    ImageDraw.Draw(image).rectangle((3, 3, 103, 103), fill="white")
    mask = Image.new("RGB", image.size, "white")
    ImageDraw.Draw(mask).rectangle((3, 3, 52, 103), fill="black")
    monkeypatch.setattr(
        "snackpress_tools.finish_appearance.render_page", lambda *args, **kwargs: (mask, None)
    )
    finish = Finish(
        id="foil",
        name="Dorure",
        mask=True,
        appearance={
            "mode": "area",
            "gradient": True,
            "alpha": 0.5,
            "color": "#ff0000",
            "end_color": "#ffffff",
            "gradient_stops": [
                {"color": "#00ff00", "position": 20},
                {"color": "#0000ff", "position": 50},
                {"color": "#000000", "position": 80},
            ],
        },
    )
    result = simulate_finishes(image, [finish], {"foil": None}, 0, 72, region=(3, 3, 104, 104))
    assert result.getpixel((23, 50)) == (127, 255, 127)
    assert result.getpixel((83, 50)) == (255, 255, 255)
    assert result.getpixel((1, 50)) == (0, 0, 255)


@pytest.mark.parametrize("positions", [[0, 40, 100], [40, 40, 75]])
def test_gradient_steps_can_meet_for_hard_transitions(positions):
    finish = Finish(
        id="foil",
        name="Dorure",
        appearance={
            "mode": "area",
            "gradient": True,
            "alpha": 1,
            "color": "#ff0000",
            "end_color": "#ffffff",
            "gradient_stops": [
                {"color": color, "position": position}
                for color, position in zip(["#00ff00", "#0000ff", "#000000"], positions)
            ],
        },
    )
    result = simulate_finishes(Image.new("RGB", (101, 11), "white"), [finish], {}, 0, 72)
    assert result.getpixel((40, 5)) == (0, 0, 255)
    assert result.getpixel((100, 5)) == (255, 255, 255)


@pytest.mark.parametrize(
    "positions", [[25, 50], [10, 25, 50, 75], [-1, 50, 75], [25, 50, 101], [50, 25, 75]]
)
def test_gradient_stop_validation(positions):
    with pytest.raises(ValidationError):
        FinishAppearance(gradient_stops=[{"color": "#ffffff", "position": p} for p in positions])
    with pytest.raises(ValidationError):
        FinishAppearance(gradient_stops=[{"color": "red", "position": p} for p in [25, 50, 75]])


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
        mode=mode,
        gradient=True,
        alpha=0.6,
        color="#ff0000",
        dash_color="#0000ff",
        gradient_stops=[
            {"color": "#00ff00", "position": 12},
            {"color": "#0000ff", "position": 47},
            {"color": "#ffff00", "position": 83},
        ],
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
        # Finishes are transparent overlays. Their alpha is zero in the bleed;
        # the unmodified native PDF underneath supplies the original artwork.
        overlays = [
            obj for obj in dict(pdf.pages[1].Resources.XObject).values() if obj.Subtype == "/Image"
        ]
        assert overlays
        for overlay in overlays:
            alpha = pikepdf.PdfImage(overlay.SMask).as_pil_image()
            assert alpha.getpixel((1, alpha.height // 2)) == 0
        assert any(
            obj.get("/SnackpressRole") == "/Artwork"
            for obj in dict(pdf.pages[2].Resources.XObject).values()
        )
    frozen = json.loads((output / "reglages.json").read_text())["settings"]["product_snapshot"]
    saved = next(f for f in frozen["finishes"] if f["id"] == finish.id)
    assert saved["appearance"] == finish.appearance.model_dump()
    assert [path.read_bytes() for path in files] == original_bytes
