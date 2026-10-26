import json

import pytest
from PIL import Image
from pydantic import ValidationError
from snackpress_tools.finish_appearance import simulate_finishes
from snackpress_tools.preview import render
from snackpress_tools.products import Finish, FinishAppearance, FinishPlacement, Snapshot
from snackpress_tools.runner import run
from test_products import artwork, content, specification


@pytest.mark.parametrize("mode", ["circle", "rectangle"])
@pytest.mark.parametrize("dpi", [127, 254])
def test_shapes_have_physical_dimensions_repeated_positions_and_page_scope(mode, dpi):
    factor = dpi / 25.4
    image = Image.new("RGBA", (round(50 * factor), round(40 * factor)))
    finish = Finish(
        id="shape",
        name="Façonnage",
        appearance={
            "mode": mode,
            "diameter": 6,
            "width": 8,
            "height": 4,
            "color": "#ff0000",
        },
    )
    placements = [
        FinishPlacement(finish_id="shape", component_id="c", x=5, y=7),
        FinishPlacement(finish_id="shape", component_id="c", x=25, y=20, page=2),
    ]
    # 3 mm bleed around a 44 × 34 mm finished format.
    region = tuple(round(n * factor) for n in (3, 3, 47, 37))
    for page in (0, 1):
        result = simulate_finishes(
            image, [finish], {}, page, dpi, region=region, finish_placements=placements
        )

        def pixel(x, y):
            return result.getpixel((round((3 + x) * factor), round((3 + y) * factor)))

        assert pixel(8, 9) == (255, 0, 0, 255)
        assert pixel(28, 22)[3] == (255 if page == 1 else 0)
        assert pixel(4, 9)[3] == pixel(14, 9)[3] == pixel(8, 14)[3] == 0
        assert pixel(5, 7)[3] == (0 if mode == "circle" else 255)
        assert result.getpixel((1, 1))[3] == 0


@pytest.mark.parametrize("field", ["diameter", "width", "height"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), 5001])
def test_shape_dimensions_are_positive_and_finite(field, value):
    with pytest.raises(ValidationError):
        FinishAppearance(mode="circle", **{field: value})


def shape_snapshot():
    snapshot = specification()
    snapshot.variant.finish_ids = ["perforation", "staple"]
    for finish in snapshot.finishes:
        if finish.id == "perforation":
            finish.appearance = FinishAppearance(mode="circle", diameter=6)
        if finish.id == "staple":
            finish.appearance = FinishAppearance(mode="rectangle", width=10, height=2)
    snapshot.variant.finish_placements = [
        FinishPlacement(finish_id="perforation", component_id="card", x=5, y=7, page=1),
        FinishPlacement(finish_id="perforation", component_id="card", x=65, y=7, page=1),
        FinishPlacement(finish_id="staple", component_id="card", x=30, y=20),
    ]
    return snapshot


@pytest.mark.parametrize(
    "patch,match",
    [
        ({"finish_id": "missing"}, "non sélectionné"),
        ({"component_id": "missing"}, "non sélectionné"),
        ({"x": -1}, "greater than"),
        ({"x": 80}, "format fini"),
        ({"y": 50}, "format fini"),
        ({"page": 0}, "greater than"),
        ({"page": 3}, "page du façonnage"),
    ],
)
def test_invalid_shape_placements_are_rejected(patch, match):
    data = shape_snapshot().model_dump()
    data["variant"]["finish_placements"][0].update(patch)
    with pytest.raises(ValidationError, match=match):
        Snapshot.model_validate(data)


def test_shapes_require_positions_but_allow_repeated_finish():
    snapshot = shape_snapshot()
    assert len(Snapshot.model_validate(snapshot.model_dump()).variant.finish_placements) == 3
    snapshot.variant.finish_placements = []
    with pytest.raises(ValidationError, match="au moins une position"):
        Snapshot.model_validate(snapshot.model_dump())
    data = shape_snapshot().model_dump()
    data["variant"]["finish_placements"] *= 100
    with pytest.raises(ValidationError, match="200"):
        Snapshot.model_validate(data)
    data = shape_snapshot().model_dump()
    data["finishes"][-1]["appearance"]["mode"] = "area"
    with pytest.raises(ValidationError, match="occurrences"):
        Snapshot.model_validate(data)


def test_manufacturing_sheet_keeps_shape_dimensions_and_every_position(tmp_path):
    snapshot = shape_snapshot()
    run(tmp_path, "kebab", [], {"product_snapshot": snapshot.model_dump()})
    text = " ".join(content(tmp_path / "fiche-fabrication.pdf").split())
    assert "diamètre 6 mm" in text and "10 × 2 mm" in text
    assert "X 5, Y 7 mm" in text and "X 65, Y 7 mm" in text
    assert "X 30, Y 20 mm" in text
    assert "page 1" in text and "toutes les pages" in text


@pytest.mark.parametrize("preview", [False, True])
def test_shapes_render_in_proof_on_correct_components_and_pages_and_are_frozen(
    tmp_path,
    monkeypatch,
    preview,
):
    from snackpress_tools import proof_render

    snapshot = shape_snapshot()
    second = snapshot.variant.components[0].model_copy(deep=True, update={"id": "second"})
    snapshot.variant.components.append(second)
    snapshot = Snapshot.model_validate(snapshot.model_dump())
    files = artwork(tmp_path, snapshot)
    original = [p.read_bytes() for p in files]
    overlays = []
    real_overlay = proof_render.finish_overlay

    def overlay(item, scale):
        result = real_overlay(item, scale)
        if item.visual:
            overlays.append((item, result))
        return result

    monkeypatch.setattr(proof_render, "finish_overlay", overlay)
    output = tmp_path / "out"
    output.mkdir()
    (render if preview else run)(
        output, "burger", files, {"product_snapshot": snapshot.model_dump()}
    )
    # Two card faces in both composite sections; second component has none.
    assert len(overlays) == 4
    for item, image in overlays:
        assert "composant-1" in str(item.source)
        left, top, right, bottom = proof_render.trim_pixels(item, image)
        factor_x, factor_y = (right - left) / 85, (bottom - top) / 55

        def alpha(x, y):
            return image.getpixel((round(left + x * factor_x), round(top + y * factor_y)))[3]

        assert alpha(8, 10) == alpha(68, 10) == (255 if item.finish_page == 0 else 0)
        assert alpha(35, 21) == 255
        assert alpha(20, 15) == 0
    text = content(output / "bat.pdf")
    assert "diamètre 6 mm" in text and "10 × 2 mm" in text
    assert "X 65, Y 7 mm" in text
    frozen = json.loads((output / "reglages.json").read_text())["settings"]["product_snapshot"]
    assert (
        frozen["variant"]["finish_placements"] == snapshot.variant.model_dump()["finish_placements"]
    )
    assert [p.read_bytes() for p in files] == original
