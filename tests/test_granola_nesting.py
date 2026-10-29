import json
from collections import Counter

import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image, ImageDraw
from reportlab.lib.units import mm
from shapely import Polygon, box, unary_union
from shapely.affinity import translate
from snackpress_tools.catalog import Granola, GranolaItem
from snackpress_tools.granola import layout_score, pack
from snackpress_tools.granola_nesting import nest, oriented
from snackpress_tools.granola_shapes import detect
from snackpress_tools.preview import render
from snackpress_tools.runner import run


def source_pdf(path, points, width=60, height=80, label=False, offset=(0, 0)):
    with pikepdf.Pdf.new() as pdf:
        page = pdf.add_blank_page(page_size=(width * mm, height * mm))
        commands = [f"1 1 1 rg 0 0 {width * mm} {height * mm} re f", "0 0 0 1 k"]
        commands += [
            f"{(x + offset[0]) * mm} {(y + offset[1]) * mm} " + ("m" if index == 0 else "l")
            for index, (x, y) in enumerate(points)
        ]
        commands.append("h f")
        if label:
            font = pdf.make_indirect(
                pikepdf.Dictionary(
                    Type=pikepdf.Name.Font,
                    Subtype=pikepdf.Name.Type1,
                    BaseFont=pikepdf.Name.Helvetica,
                )
            )
            page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
            commands.append(
                f"1 1 1 rg BT /F1 8 Tf {(5 + offset[0]) * mm} "
                f"{(60 + offset[1]) * mm} Td (TRIANGLE) Tj ET"
            )
        page.Contents = pikepdf.Stream(pdf, "\n".join(commands).encode())
        pdf.save(path)


def triangle(path, corner="tl", label=False):
    vertices = {"tl": (0, 80), "tr": (60, 80), "bl": (0, 0), "br": (60, 0)}
    missing = {"tl": "br", "tr": "bl", "bl": "tr", "br": "tl"}[corner]
    source_pdf(path, [vertices[c] for c in ("bl", "br", "tr", "tl") if c != missing], label=label)


def execute(folder, files, settings):
    folder.mkdir()
    result = run(folder, "granola", files, settings)
    return result, json.loads((folder / "plan-imposition.json").read_text())


def placed_geometry(source, pose):
    shape = unary_union([Polygon(p) for p in source["outline"]])
    return translate(oriented(shape, pose["rotation"]), xoff=pose["x"], yoff=pose["y"])


def assert_contours(plan, gap, margin):
    size = plan["sheet_format"]["output"]
    frame = box(margin, margin, size["width"] - margin, size["height"] - margin)
    for poses in plan["sheets"]:
        placed = [placed_geometry(plan["sources"][pose["file"]], pose) for pose in poses]
        for i, shape in enumerate(placed):
            assert frame.buffer(1e-5).covers(shape)
            for other in placed[i + 1 :]:
                assert shape.intersection(other).area < 1e-4
                assert shape.distance(other) >= gap - 1e-4


def black_area(path):
    with pdfium.PdfDocument(str(path)) as pdf:
        total = 0
        for page in pdf:
            bitmap = page.render(scale=3)
            pixels = np.asarray(bitmap.to_pil().convert("RGB"))
            total += np.count_nonzero(np.max(pixels, axis=2) < 128)
            bitmap.close()
        return total


@pytest.mark.parametrize("corner", ["tl", "tr", "bl", "br"])
def test_automatic_triangles_nest_without_rasterizing_or_covering_the_other_copy(tmp_path, corner):
    source = tmp_path / "triangle.pdf"
    triangle(source, corner, label=corner == "tl")
    settings = {
        "sheet_width": 130,
        "sheet_height": 100,
        "margin": 5,
        "gap": 3,
        "optimization": "area",
        "crop": "margin",
        "items": [{"quantity": 2}],
    }
    result, plan = execute(tmp_path / "nested", [source], settings)
    assert result.metrics["Planches"] == 1
    assert result.metrics["Paires imbriquées"] == 1
    assert result.shapes[0].kind == "triangle"
    assert 0 < result.metrics["Surface utilisée (%)"] <= 100
    assert len(plan["sheets"][0]) == 2
    assert any(p["rotation"] in (180, 270) for p in plan["sheets"][0])
    assert_contours(plan, 3, 5)
    first, second = plan["sheets"][0]
    assert (
        box(first["x"], first["y"], first["x"] + first["width"], first["y"] + first["height"])
        .intersection(
            box(
                second["x"],
                second["y"],
                second["x"] + second["width"],
                second["y"] + second["height"],
            )
        )
        .area
        > 3000
    )
    assert black_area(tmp_path / "nested/imposition.pdf") == pytest.approx(
        2 * black_area(source), rel=0.015
    )
    with pikepdf.open(tmp_path / "nested/imposition.pdf") as pdf:
        assert not pdf.check_pdf_syntax()
        assert all(
            str(form.Subtype) == "/Form" for _, form in pdf.pages[0].Resources.XObject.items()
        )
        assert all(
            "/XObject" not in form.Resources for _, form in pdf.pages[0].Resources.XObject.items()
        )
    if corner == "tl":
        with pdfium.PdfDocument(str(tmp_path / "nested/imposition.pdf")) as pdf:
            assert pdf[0].get_textpage().get_text_range().count("TRIANGLE") == 2
    rectangle, _ = execute(
        tmp_path / "rectangle",
        [source],
        {**settings, "items": [{"quantity": 2, "shape": "rectangle"}]},
    )
    assert rectangle.metrics["Planches"] == 2
    assert rectangle.metrics["Paires imbriquées"] == 0


@pytest.mark.parametrize(
    "points,width,height",
    [
        ([(0, 0), (60, 0), (60, 20), (20, 20), (20, 80), (0, 80)], 130, 120),
        ([(30, 0), (60, 40), (30, 80), (0, 40)], 110, 140),
    ],
)
def test_other_contours_and_concave_shapes_are_detected_and_nested(tmp_path, points, width, height):
    source = tmp_path / "shape.pdf"
    source_pdf(source, points)
    result, plan = execute(
        tmp_path / "out",
        [source],
        {
            "sheet_width": width,
            "sheet_height": height,
            "margin": 5,
            "gap": 3,
            "optimization": "area",
            "crop": "margin",
            "items": [{"quantity": 2}],
        },
    )
    assert result.shapes[0].kind == "contour"
    assert result.metrics["Paires imbriquées"] == 1
    assert result.metrics["Planches"] == 1
    assert_contours(plan, 3, 5)
    assert black_area(tmp_path / "out/imposition.pdf") == pytest.approx(
        2 * black_area(source), rel=0.02
    )


def test_different_files_with_complementary_contours_can_nest_without_rotation(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    triangle(a, "tl")
    triangle(b, "br")
    result, plan = execute(
        tmp_path / "out",
        [a, b],
        {
            "sheet_width": 130,
            "sheet_height": 100,
            "margin": 5,
            "gap": 3,
            "rotation": "none",
            "optimization": "area",
            "crop": "margin",
        },
    )
    assert result.metrics["Paires imbriquées"] == 1
    assert result.metrics["Planches"] == 1
    assert {p["file"] for p in plan["sheets"][0]} == {0, 1}
    assert all(p["rotation"] == 0 for p in plan["sheets"][0])
    assert_contours(plan, 3, 5)


def test_transparent_white_shapes_and_odd_quantities_keep_all_copies(tmp_path):
    source = tmp_path / "white-triangle.png"
    image = Image.new("RGBA", (300, 400), (255, 255, 255, 0))
    ImageDraw.Draw(image).polygon([(0, 0), (299, 0), (0, 399)], fill="white")
    image.save(source)
    result, plan = execute(
        tmp_path / "out",
        [source],
        {
            "sheet_width": 130,
            "sheet_height": 200,
            "margin": 5,
            "gap": 3,
            "optimization": "area",
            "crop": "margin",
            "items": [{"quantity": 5, "image_width": 60}],
        },
    )
    assert result.shapes[0].kind == "triangle"
    assert result.metrics["Paires imbriquées"] == 2
    assert sum(map(len, plan["sheets"])) == 5
    assert {p["copy"] for s in plan["sheets"] for p in s} == {1, 2, 3, 4, 5}
    assert_contours(plan, 3, 5)


def test_blank_outer_margins_are_removed_at_original_scale_and_preview_matches(tmp_path):
    source = tmp_path / "with-white-frame.pdf"
    source_pdf(source, [(0, 0), (0, 80), (60, 80)], width=80, height=100, offset=(10, 10))
    settings = {
        "sheet_width": 130,
        "sheet_height": 100,
        "margin": 5,
        "gap": 3,
        "optimization": "area",
        "crop": "margin",
        "items": [{"quantity": 2}],
    }
    final = tmp_path / "final"
    result, plan = execute(final, [source], settings)
    assert result.shapes[0].width == pytest.approx(60, abs=0.25)
    assert result.shapes[0].height == pytest.approx(80, abs=0.25)
    assert plan["sources"][0]["original_width"] == pytest.approx(80)
    assert plan["sources"][0]["original_height"] == pytest.approx(100)
    assert_contours(plan, 3, 5)
    preview = tmp_path / "preview"
    preview.mkdir()
    render(preview, "granola", [source], settings)
    assert plan == json.loads((preview / "plan-imposition.json").read_text())
    assert black_area(final / "imposition.pdf") == pytest.approx(2 * black_area(source), rel=0.015)


def test_rectangle_override_preserves_the_full_page_and_zero_gap_allows_touching(tmp_path):
    source = tmp_path / "triangle.pdf"
    triangle(source)
    result, plan = execute(
        tmp_path / "out",
        [source],
        {
            "sheet_width": 130,
            "sheet_height": 100,
            "margin": 5,
            "gap": 0,
            "optimization": "area",
            "crop": "margin",
            "items": [{"quantity": 2}],
        },
    )
    assert result.metrics["Paires imbriquées"] == 1
    assert_contours(plan, 0, 5)
    assert result.shapes[0].width == pytest.approx(60)
    assert result.shapes[0].height == pytest.approx(80)
    assert Counter(p["file"] for s in plan["sheets"] for p in s) == {0: 2}


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("unit", [1, 2])
def test_rotated_pdf_contours_preserve_physical_scale_and_visible_artwork(tmp_path, angle, unit):
    source = tmp_path / "rotated.pdf"
    triangle(source)
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.pages[0].Rotate = angle
        pdf.pages[0].UserUnit = unit
        pdf.save(source)
    result, plan = execute(
        tmp_path / "out",
        [source],
        {
            "sheet_width": 400,
            "sheet_height": 400,
            "margin": 5,
            "gap": 3,
            "optimization": "area",
            "crop": "margin",
            "items": [{"quantity": 2}],
        },
    )
    expected = (80 * unit, 60 * unit) if angle in (90, 270) else (60 * unit, 80 * unit)
    assert (result.shapes[0].width, result.shapes[0].height) == pytest.approx(expected)
    assert_contours(plan, 3, 5)
    assert black_area(tmp_path / "out/imposition.pdf") == pytest.approx(
        2 * unit**2 * black_area(source), rel=0.015
    )


def test_jpeg_shape_and_adjustable_off_white_background(tmp_path):
    source = tmp_path / "triangle.jpg"
    image = Image.new("RGB", (600, 800), (245, 245, 245))
    ImageDraw.Draw(image).polygon([(0, 0), (599, 0), (0, 799)], fill="black")
    image.save(source, quality=95)
    _, _, _, _, strict = detect(source, 0, (60, 80), 0)
    geometry, _, size, _, kind = detect(source, 0, (60, 80), 15)
    assert strict == "rectangle"
    assert kind == "triangle"
    assert size == pytest.approx((60, 80))
    assert geometry.area == pytest.approx(2400, rel=0.03)


def test_width_optimization_nests_maximum_quantity_without_extra_copies(tmp_path):
    source = tmp_path / "triangle.pdf"
    triangle(source)
    geometry, _, size, _, _ = detect(source, 0, (60, 80), 5)
    params = Granola()
    items = [GranolaItem(quantity=2000)]
    sheets, paired = nest([size], items, [geometry], params)
    assert paired == 1000
    assert len(sheets) == 50
    assert sorted(p.copy for sheet in sheets for p in sheet) == list(range(1, 2001))


@pytest.mark.parametrize("optimization", ["area", "width"])
def test_mixed_shapes_keep_counts_gaps_and_best_complete_layout(optimization):
    shapes = [
        Polygon([(0, 0), (60, 80), (0, 80)]),
        Polygon([(0, 0), (60, 0), (60, 20), (20, 20), (20, 80), (0, 80)]),
        Polygon([(30, 0), (60, 40), (30, 80), (0, 40)]),
        None,
    ]
    sizes = [(60, 80), (60, 80), (60, 80), (40, 30)]
    items = [GranolaItem(quantity=n) for n in (5, 3, 2, 4)]
    params = Granola(sheet_width=230, sheet_height=170, margin=5, gap=3, optimization=optimization)
    sheets, _ = nest(sizes, items, shapes, params)
    baseline = pack(sizes, items, params)
    before, after = [layout_score(s, params.margin, optimization) for s in (baseline, sheets)]
    assert after[:3] <= before[:3] if optimization == "width" else after <= before
    assert Counter(p.file for sheet in sheets for p in sheet) == {0: 5, 1: 3, 2: 2, 3: 4}
    assert len({(p.file, p.copy) for sheet in sheets for p in sheet}) == 14
    for sheet in sheets:
        placed = [
            translate(
                oriented(
                    shapes[p.file] if shapes[p.file] is not None else box(0, 0, *sizes[p.file]),
                    p.rotation,
                ),
                xoff=p.x,
                yoff=p.y,
            )
            for p in sheet
        ]
        for i, shape in enumerate(placed):
            assert box(5, 5, 225, 165).buffer(1e-6).covers(shape)
            assert all(shape.distance(other) >= 3 - 1e-6 for other in placed[i + 1 :])
