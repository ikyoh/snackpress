import json

import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import make_pdf, product_snapshot
from PIL import Image
from snackpress_tools.catalog import CATALOG, MODELS, Burrito, Pizza, Taco
from snackpress_tools.common import page_selection
from snackpress_tools.documents import booklet_order
from snackpress_tools.generators import eyelets, fold_widths
from snackpress_tools.runner import run


@pytest.mark.parametrize(
    "shape,radius", [("rectangle", 0), ("rectangle", 10), ("circle", 0), ("ellipse", 0)]
)
def test_pizza_contours_and_boxes(tmp_path, shape, radius):
    run(
        tmp_path,
        "pizza",
        [],
        {
            "shape": shape,
            "width": 80,
            "height": 60,
            "corner_radius": radius,
        },
    )
    height = 80 if shape == "circle" else 60
    with pikepdf.open(tmp_path / "gabarit.pdf") as doc:
        box = [float(v) * 25.4 / 72 for v in doc.pages[0].TrimBox]
        assert box == pytest.approx([3, 3, 83, height + 3])
        assert doc.pages[0].BleedBox == doc.pages[0].MediaBox
        commands = pikepdf.parse_content_stream(doc.pages[0])
        assert any(str(op) == "c" for _, op in commands) == (
            radius > 0 or shape in {"circle", "ellipse"}
        )
    with pdfium.PdfDocument(str(tmp_path / "gabarit.pdf")) as doc:
        bitmap = doc[0].render(scale=4)
        img = bitmap.to_pil().convert("RGB")

        def pixel(x, y):
            return img.getpixel((round(x * 72 / 25.4 * 4), round(y * 72 / 25.4 * 4)))

        assert pixel(43, (height + 6) / 2) == (255, 255, 255)
        # Sample the bleed just outside the curved cut, inside its bounding box.
        sample = (
            pixel(14, 14)
            if shape == "circle"
            else pixel(10, 14)
            if shape == "ellipse"
            else pixel(4, 4)
        )
        assert sample == (
            (255, 255, 255) if shape == "rectangle" and radius == 0 else (247, 229, 220)
        )
        bitmap.close()
    settings = json.loads((tmp_path / "reglages.json").read_text())["settings"]
    assert settings["height"] == height


def test_pizza_validates_curves_and_safety():
    with pytest.raises(ValueError, match="rayon"):
        Pizza(width=80, height=60, corner_radius=31)
    with pytest.raises(ValueError, match="sécurité"):
        Pizza(shape="circle", width=20, height=60, safety=10)
    assert Pizza(width=80, height=60, corner_radius=30).corner_radius == 30
    assert Pizza(shape="circle", width=80, height=10).height == 80


def test_pizza_directional_zone_validation_and_legacy_safety():
    legacy = Pizza(safety=7)
    assert all(
        getattr(legacy, f"safety_{side}") == 7 for side in ("top", "bottom", "left", "right")
    )
    mixed = Pizza(safety=7, safety_top=2, safety_left=0)
    assert mixed.safety_top == 2 and mixed.safety_bottom == 7 and mixed.safety_left == 0
    for settings in (
        {"safety_left": 50, "safety_right": 35},
        {"safety_top": 30, "safety_bottom": 25},
        {"unusable_left": 50, "unusable_right": 35},
        {"unusable_top": 30, "unusable_bottom": 25},
        {"unusable_left": -1},
    ):
        with pytest.raises(ValueError):
            Pizza(**settings)


@pytest.mark.parametrize(
    "shape,radius", [("rectangle", 0), ("rectangle", 10), ("circle", 0), ("ellipse", 0)]
)
def test_pizza_directional_safety_and_clipped_yellow_hatching(tmp_path, shape, radius):
    run(
        tmp_path,
        "pizza",
        [],
        {
            "shape": shape,
            "corner_radius": radius,
            "width": 80,
            "height": 60,
            "safety_top": 4,
            "safety_bottom": 6,
            "safety_left": 3,
            "safety_right": 5,
            "unusable_top": 7,
            "unusable_bottom": 3,
            "unusable_left": 5,
            "unusable_right": 2,
        },
    )
    height = 80 if shape == "circle" else 60
    scale = 2
    with pdfium.PdfDocument(str(tmp_path / "gabarit.pdf")) as doc:
        bitmap = doc[0].render(scale=scale)
        pixels = np.array(bitmap.to_pil().convert("RGB"))
        bitmap.close()
    yellow = (pixels[:, :, 0] > 180) & (pixels[:, :, 1] > 130) & (pixels[:, :, 2] < 80)
    rows, columns = np.where(yellow)
    assert len(rows) > 100
    x = columns / scale * 25.4 / 72 - 3
    y = height + 3 - rows / scale * 25.4 / 72
    assert x.min() > -0.3 and x.max() < 80.3
    assert y.min() > -0.3 and y.max() < height + 0.3
    # The open centre contains no hatching; all four requested bands do.
    assert not np.any((x > 5.5) & (x < 77.5) & (y > 3.5) & (y < height - 7.5))
    for region in (x < 4.5, x > 78.5, y < 2.5, y > height - 6.5):
        assert np.count_nonzero(region) > 10
    if shape in {"circle", "ellipse"}:
        assert np.all(((x - 40) / 40) ** 2 + ((y - height / 2) / (height / 2)) ** 2 < 1.03)
    with pikepdf.open(tmp_path / "gabarit.pdf") as doc:
        commands = pikepdf.parse_content_stream(doc.pages[0])
        if shape == "rectangle" and radius == 0:
            rectangles = [
                [float(value) * 25.4 / 72 for value in args]
                for args, op in commands
                if str(op) == "re"
            ]
            assert any(values == pytest.approx([6, 9, 72, 50]) for values in rectangles)
        assert any(str(op) == "W*" for _, op in commands)


@pytest.mark.parametrize("axis", ["width", "height"])
def test_pizza_bounded_dimensions(axis):
    settings = {f"{axis}_mode": "bounded", f"{axis}_min": 40, f"{axis}_max": 100}
    for value in (40, 70, 100):
        assert getattr(Pizza(**settings, **{axis: value}), axis) == value
    for value in (39.9, 100.1):
        with pytest.raises(ValueError, match="comprise entre"):
            Pizza(**settings, **{axis: value})
    with pytest.raises(ValueError, match="borne minimale"):
        Pizza(**{**settings, f"{axis}_min": 101})
    # Bounds do not constrain a dimension after switching back to fixed mode.
    assert getattr(Pizza(**{**settings, f"{axis}_mode": "fixed", axis: 120}), axis) == 120


def test_pizza_circle_uses_diameter_bounds_only():
    pizza = Pizza(
        shape="circle",
        width=70,
        width_mode="bounded",
        width_min=50,
        width_max=100,
        height_mode="bounded",
        height_min=200,
        height_max=300,
    )
    assert pizza.width == pizza.height == 70
    with pytest.raises(ValueError, match="comprise entre"):
        Pizza(shape="circle", width=110, width_mode="bounded", width_min=50, width_max=100)


@pytest.mark.parametrize("tool", list(CATALOG))
def test_every_tool_produces_readable_deliverables(tool, tmp_path, source):
    folder = tmp_path / tool
    folder.mkdir()
    count = CATALOG[tool].min_files
    settings = {"product_snapshot": product_snapshot()} if tool == "kebab" else {}
    result = run(folder, tool, [source] * count, settings)
    assert result.tool == tool
    assert result.summary and result.warnings
    for item in result.artifacts:
        path = folder / item.name
        assert path.is_file() and path.stat().st_size > 0
        if path.suffix == ".pdf":
            with pikepdf.open(path) as doc:
                assert len(doc.pages) == item.pages
                assert not doc.check_pdf_syntax()
            with pdfium.PdfDocument(str(path)) as doc:
                assert len(doc) >= 1
                page = doc[0]
                bitmap = page.render(scale=0.15)
                assert bitmap.width > 0
                bitmap.close()
        elif path.suffix == ".json":
            json.loads(path.read_text())


def test_booklet_order_and_native_content(tmp_path):
    src = tmp_path / "booklet.pdf"
    make_pdf(src, pages=8)
    out = tmp_path / "booklet"
    out.mkdir()
    result = run(
        out,
        "layer-cake",
        [src],
        {"mode": "booklet", "quantity": 3, "sheet_width": 420, "sheet_height": 297},
    )
    assert booklet_order(8) == [[7, 0, 1, 6], [5, 2, 3, 4]]
    assert result.metrics["Feuilles à tirer"] == 6
    with pikepdf.open(out / "imposition.pdf") as doc:
        assert len(doc.pages) == 4
        assert len(doc.pages[0].Resources.XObject) == 2
    make_pdf(src, pages=6)
    with pytest.raises(ValueError, match="multiple de 4"):
        run(out, "layer-cake", [src], {"mode": "booklet", "sheet_width": 15})


def test_comparison_identical_and_missing_pages(tmp_path, source):
    out = tmp_path / "compare"
    out.mkdir()
    run(out, "tiramisu", [source, source], {})
    data = json.loads((out / "comparaison.json").read_text())
    assert all(p["difference_percent"] == 0 for p in data["pages"])
    other = tmp_path / "one.pdf"
    make_pdf(other, pages=1)
    run(out, "tiramisu", [source, other], {})
    data = json.loads((out / "comparaison.json").read_text())
    assert data["pages"][1]["difference_percent"] == 100


def test_donut_edge_and_mirror_pixels(tmp_path):
    src = tmp_path / "image.png"
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:, :10] = [255, 0, 0]
    image[:, 10:] = [0, 0, 255]
    Image.fromarray(image).save(src)
    for method in ("edge", "mirror"):
        out = tmp_path / method
        out.mkdir()
        run(
            out,
            "donut",
            [src],
            {"bleed": 10, "image_width": 25.4, "dpi": 100, "method": method, "output": "png"},
        )
        img = np.asarray(Image.open(out / "fond-perdu.png"))
        assert img.shape == (178, 178, 3)
        assert list(img[70, 0]) == ([255, 0, 0] if method == "edge" else [0, 0, 255])


def test_sushi_spot_names_and_vectors(tmp_path):
    run(tmp_path, "sushi", [], {"creases": "20,60"})
    with pikepdf.open(tmp_path / "contours.pdf") as doc:
        colors = [v for _, v in doc.pages[0].Resources.ColorSpace.items()]
        assert {str(v[1]) for v in colors} == {"/CutContour", "/Crease"}
        assert all(str(v[0]) == "/Separation" for v in colors)
        assert "/XObject" not in doc.pages[0].Resources


@pytest.mark.parametrize("code", ["none", "code128"])
def test_fortune_sequence_and_count_limit(tmp_path, code):
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {"count": 3, "start": 8, "code": code, "payload": "{n}"},
    )
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as doc:
        assert len(doc) == 3
        text = doc[2].get_textpage().get_text_range()
        assert text.strip() == "SP-0010"
    with pytest.raises(ValueError):
        MODELS["fortune-cookie"](count=1001)


@pytest.mark.parametrize(
    "settings",
    [{}, {"text": "Votre invitation", "code": "qr"}, {"code": "code128", "payload": "{n}"}],
)
def test_fortune_only_adds_numbering_by_default_and_with_legacy_settings(tmp_path, settings):
    run(tmp_path, "fortune-cookie", [], {"count": 1, **settings})
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as doc:
        assert doc[0].get_textpage().get_text_range().strip() == "SP-0001"
    with pikepdf.open(tmp_path / "serie.pdf") as doc:
        operations = pikepdf.parse_content_stream(doc.pages[0])
        # No QR graphics or white masks covering the imported artwork.
        assert not any(str(op) in {"f", "f*", "Do"} for _, op in operations)
    saved = json.loads((tmp_path / "reglages.json").read_text())["settings"]
    assert not {"code", "payload", "text"}.intersection(saved)


def test_bento_order_rotation_and_signatures_removed(tmp_path, source):
    run(tmp_path, "bento", [source], {"operation": "reorder", "pages": "2,1"})
    with pdfium.PdfDocument(str(tmp_path / "assemblage.pdf")) as doc:
        assert "VERSO" in doc[0].get_textpage().get_text_range()
    run(tmp_path, "bento", [source], {"operation": "rotate", "pages": "1", "rotation": 90})
    with pikepdf.open(tmp_path / "assemblage.pdf") as doc:
        assert int(doc.pages[0].Rotate) == 90
        assert "/AcroForm" not in doc.Root
    with pytest.raises(ValueError, match="chaque page"):
        run(tmp_path, "bento", [source], {"operation": "reorder", "pages": "1,1"})


def test_folding_sum_eyelet_spacing_and_spine(tmp_path):
    for fold in ("accordion", "roll", "gate"):
        widths = fold_widths(Taco(fold=fold))
        assert sum(widths) == pytest.approx(297)
        assert min(widths) > 0
    p = Burrito()
    points = eyelets(p)
    assert len(points) == len(set(points))
    assert len(eyelets(Burrito(width=2000.123456, height=1000.123456, inset=20.112233))) == 12
    horizontal = sorted(x for x, y in points if y == p.inset)
    assert max(b - a for a, b in zip(horizontal, horizontal[1:])) <= p.spacing
    result = run(tmp_path, "club-sandwich", [], {})
    assert result.metrics["Dos estimé (mm)"] == 6.9
    assert page_selection("3, 1-2", 3) == [2, 0, 1]


def test_fortune_background_remains_visible(tmp_path):
    src = tmp_path / "fond.pdf"
    make_pdf(src, pages=1)
    out = tmp_path / "variable"
    out.mkdir()
    run(out, "fortune-cookie", [src], {"count": 2})
    with pikepdf.open(out / "serie.pdf") as doc:
        assert len(doc.pages) == 2
        assert len(doc.pages[0].Resources.XObject) == 2
    with pdfium.PdfDocument(str(out / "serie.pdf")) as doc:
        bitmap = doc[0].render(scale=1, rev_byteorder=True)
        pixel = bitmap.to_pil().convert("RGB").getpixel((210, 70))
        assert min(pixel) < 200  # Background outside the variable fields survives.
        bitmap.close()


def test_poke_known_red_screen_estimate(tmp_path):
    src = tmp_path / "red.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(72, 72))
    page.Contents = pikepdf.Stream(pdf, b"1 0 0 rg 0 0 72 72 re f")
    pdf.save(src)
    out = tmp_path / "colors"
    out.mkdir()
    run(out, "poke", [src], {})
    data = json.loads((out / "couleurs.json").read_text())
    assert data["pages"][0]["mean_cmyk_percent"] == pytest.approx([0, 100, 100, 0])
    assert data["pages"][0]["color_spaces"] == ["/DeviceRGB"]


def test_fortune_multiple_numberings_styles_and_sequence(tmp_path):
    placements = [
        {"x": 12, "y": 20, "color": "#ff0000", "size": 18, "font": "Courier", "rotation": 90},
        {"x": 40, "y": 35, "color": "#0000ff", "size": 12, "font": "Times-Roman", "rotation": -30},
        {"x": 5, "y": 50, "color": "#00ff00", "size": 10, "font": "Snack", "rotation": 0},
    ]
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {
            "count": 2,
            "start": 9,
            "code": "none",
            "numberings": placements,
        },
    )
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as doc:
        for index, page in enumerate(doc):
            assert page.get_textpage().get_text_range().count(f"SP-{9 + index:04d}") == 3
    with pikepdf.open(tmp_path / "serie.pdf") as doc:
        operations = pikepdf.parse_content_stream(doc.pages[0])
        colors = [list(args) for args, op in operations if str(op) == "rg"]
        assert [1, 0, 0] in colors and [0, 0, 1] in colors and [0, 1, 0] in colors
        matrices = [list(map(float, args)) for args, op in operations if str(op) == "cm"]
        assert any(
            m[:4] == pytest.approx([0, -1, 1, 0])
            and m[4:] == pytest.approx([12 * 72 / 25.4, 35 * 72 / 25.4], abs=0.001)
            for m in matrices
        )
        fonts = {str(font.BaseFont) for _, font in doc.pages[0].Resources.Font.items()}
        assert "/Courier" in fonts and "/Times-Roman" in fonts
    settings = json.loads((tmp_path / "reglages.json").read_text())["settings"]
    assert settings["numberings"] == placements


def test_fortune_numberings_without_fixed_limit_and_empty_list(tmp_path):
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {
            "count": 1,
            "code": "none",
            "numberings": [{"x": 5, "y": 20}] * 125,
        },
    )
    with pikepdf.open(tmp_path / "serie.pdf") as doc:
        operations = pikepdf.parse_content_stream(doc.pages[0])
        assert (
            sum(str(op) == "Tj" and bytes(args[0]) == b"SP-0001" for args, op in operations) == 125
        )
    run(tmp_path, "fortune-cookie", [], {"count": 1, "code": "none", "numberings": []})
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as doc:
        assert "SP-0001" not in doc[0].get_textpage().get_text_range()


@pytest.mark.parametrize(
    "placement",
    [
        {"x": 86},
        {"y": 56},
        {"size": 0},
        {"color": "red"},
        {"font": "unknown"},
        {"rotation": 361},
        {"x": float("nan")},
    ],
)
def test_fortune_invalid_numbering(placement):
    with pytest.raises(ValueError):
        MODELS["fortune-cookie"](numberings=[placement])
