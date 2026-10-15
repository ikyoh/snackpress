import json

import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import make_pdf
from PIL import Image
from snackpress_tools.catalog import CATALOG, MODELS, Burrito, Taco
from snackpress_tools.common import page_selection
from snackpress_tools.documents import booklet_order
from snackpress_tools.generators import eyelets, fold_widths
from snackpress_tools.runner import run


@pytest.mark.parametrize("tool", list(CATALOG))
def test_every_tool_produces_readable_deliverables(tool, tmp_path, source):
    folder = tmp_path / tool
    folder.mkdir()
    count = CATALOG[tool].min_files
    result = run(folder, tool, [source] * count, {})
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


def test_fortune_sequence_and_count_limit(tmp_path):
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {"count": 3, "start": 8, "code": "code128", "payload": "{n}"},
    )
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as doc:
        assert len(doc) == 3
        text = doc[2].get_textpage().get_text_range()
        assert "SP-0010" in text
    with pytest.raises(ValueError):
        MODELS["fortune-cookie"](count=101)


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
