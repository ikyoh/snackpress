import json

import numpy as np
import pikepdf
import pytest
from reportlab.lib.units import mm
from snackpress_tools.burger import template
from snackpress_tools.catalog import Burger, Sushi
from snackpress_tools.common import dimensions
from snackpress_tools.proof_layout import guide_key
from snackpress_tools.runner import run


def commands_in_mm(page, name):
    return [
        [float(v) / mm for v in args]
        for args, op in pikepdf.parse_content_stream(page)
        if str(op) == name
    ]


@pytest.mark.parametrize("shape", ["none", "rectangle", "circle"])
@pytest.mark.parametrize("bleed", [0, 3])
def test_sushi_bleed_boxes_and_optional_contour(tmp_path, shape, bleed):
    run(tmp_path, "sushi", [], {"shape": shape, "width": 80, "height": 80, "bleed": bleed})
    with pikepdf.open(tmp_path / "contours.pdf") as pdf:
        page = pdf.pages[0]
        assert dimensions(page) == pytest.approx((80 + 2 * bleed, 80 + 2 * bleed))
        assert [float(v) / mm for v in page.TrimBox] == pytest.approx(
            [bleed, bleed, 80 + bleed, 80 + bleed]
        )
        assert page.BleedBox == page.MediaBox
        ops = [str(op) for _, op in pikepdf.parse_content_stream(page)]
        assert ops.count("S") == (0 if shape == "none" else 1)
        assert ("re" in ops) == (shape == "rectangle")
        assert ("c" in ops) == (shape == "circle")
        assert not any(op in {"f", "f*", "B", "B*"} for op in ops)


def test_sushi_four_line_types_use_named_spots_and_top_left_origin(tmp_path):
    lines = [
        {"kind": "cut", "axis": "vertical", "position": 10},
        {"kind": "crease", "axis": "horizontal", "position": 15},
        {"kind": "cut", "axis": "horizontal", "position": 55},
        {"kind": "crease", "axis": "vertical", "position": 85},
    ]
    result = run(
        tmp_path,
        "sushi",
        [],
        {
            "bleed": 4,
            "lines": json.dumps(lines),
            "cut_name": "Cut",
            "crease_name": "Fold",
        },
    )
    assert result.metrics == {"Rainages": 2, "Coupes": 2}
    with pikepdf.open(tmp_path / "contours.pdf") as pdf:
        page = pdf.pages[0]
        assert commands_in_mm(page, "m") == pytest.approx(
            np.array([[14, 4], [4, 44], [4, 4], [89, 4]])
        )
        assert commands_in_mm(page, "l") == pytest.approx(
            np.array([[14, 59], [89, 44], [89, 4], [89, 59]])
        )
        spaces = {str(key): str(value[1]) for key, value in page.Resources.ColorSpace.items()}
        ink = None
        strokes = []
        for args, op in pikepdf.parse_content_stream(page):
            if str(op) == "CS":
                ink = spaces[str(args[0])]
            if str(op) == "S":
                strokes.append(ink)
        assert strokes == ["/Cut", "/Fold", "/Cut", "/Fold"]
        assert "/XObject" not in page.Resources
        assert any(bool(state.get("/OP")) for _, state in page.Resources.ExtGState.items())
        assert commands_in_mm(page, "w")[-1] == pytest.approx([0.1], abs=1e-6)


@pytest.mark.parametrize("width,height,radius", [(80, 80, 10), (85, 55, 27.5)])
def test_sushi_rounded_contour_preserves_size_and_spot(tmp_path, width, height, radius):
    run(
        tmp_path,
        "sushi",
        [],
        {
            "width": width,
            "height": height,
            "bleed": 3,
            "shape": "rectangle",
            "corner_radius": radius,
        },
    )
    with pikepdf.open(tmp_path / "contours.pdf") as pdf:
        page = pdf.pages[0]
        assert dimensions(page) == pytest.approx((width + 6, height + 6))
        assert [float(v) / mm for v in page.TrimBox] == pytest.approx([3, 3, width + 3, height + 3])
        assert commands_in_mm(page, "m")[0] == pytest.approx([3 + radius, 3])
        assert len(commands_in_mm(page, "c")) == 4
        assert {str(value[1]) for _, value in page.Resources.ColorSpace.items()} == {"/CutContour"}
        assert "/XObject" not in page.Resources
    saved = json.loads((tmp_path / "reglages.json").read_text())["settings"]
    assert saved["corner_radius"] == radius


@pytest.mark.parametrize("radius", [-1, 28, float("nan"), float("inf")])
def test_sushi_rejects_invalid_corner_radius(radius):
    with pytest.raises(ValueError):
        Sushi(shape="rectangle", corner_radius=radius)


def test_sushi_default_and_legacy_settings():
    assert Sushi().shape == "none"
    assert guide_key("sushi", {}) == []
    saved = Sushi(creases="20, 60", shape="rectangle").model_dump()
    assert "creases" not in saved
    assert saved["lines"] == [
        {"kind": "crease", "axis": "vertical", "position": 20},
        {"kind": "crease", "axis": "vertical", "position": 60},
    ]
    assert Sushi.model_validate(saved).model_dump() == saved
    assert len(guide_key("sushi", saved)) == 2


@pytest.mark.parametrize(
    "settings",
    [
        {"bleed": -1},
        {"bleed": 31},
        {"lines": [{"axis": "vertical", "position": 86}]},
        {"lines": [{"axis": "horizontal", "position": 56}]},
        {"lines": [{"position": -1}]},
        {"lines": [{"position": float("nan")}]},
        {"lines": [{"position": float("inf")}]},
        {"lines": [{"kind": "other"}]},
        {"lines": [{"axis": "diagonal"}]},
        {"lines": "not json"},
        {"lines": "{}"},
    ],
)
def test_sushi_rejects_invalid_geometry(settings):
    with pytest.raises(ValueError):
        Sushi.model_validate(settings)


def test_sushi_has_no_fixed_line_count_limit(tmp_path):
    lines = [{"kind": "crease", "axis": "vertical", "position": i / 2} for i in range(151)]
    run(tmp_path, "sushi", [], {"lines": lines})
    with pikepdf.open(tmp_path / "contours.pdf") as pdf:
        assert len(commands_in_mm(pdf.pages[0], "l")) == 151


def test_sushi_burger_guide_origin_includes_bleed(tmp_path):
    _, size, trim = template(
        tmp_path,
        [],
        Burger(
            template_tool="sushi",
            template_settings={"bleed": 3},
        ),
    )
    assert size == pytest.approx((91, 61))
    assert trim == (3, 3, 85, 55)
