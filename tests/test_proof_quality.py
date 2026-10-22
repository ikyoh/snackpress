"""The proof keeps native PDF content and only rasterizes finishing simulations."""

from io import BytesIO

import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from snackpress_tools.common import new_canvas
from snackpress_tools.products import FinishAppearance
from snackpress_tools.runner import run
from test_products import artwork, specification


def xobjects(resources):
    for obj in dict(resources.get("/XObject", {})).values():
        yield obj
        if obj.Subtype == "/Form":
            yield from xobjects(obj.get("/Resources", {}))


@pytest.mark.parametrize("with_image", [False, True])
def test_original_text_paths_colors_and_image_resolution_survive(tmp_path, with_image):
    source = tmp_path / "native.pdf"
    c = new_canvas(source, 91, 61)
    c.setFont("Snack", 9)
    c.drawString(10 * mm, 40 * mm, "TEXTE SOURCE VECTORIEL")
    c.setStrokeColorCMYK(0.2, 0.7, 0.4, 0.1)
    c.circle(45 * mm, 25 * mm, 4 * mm)
    if with_image:
        # A small printed photograph with substantially more detail than the old
        # 1100px raster cap: preserve its encoded bytes, not just its dimensions.
        pixels = np.random.default_rng(7).integers(0, 256, (900, 1800, 3), dtype=np.uint8)
        jpeg = BytesIO()
        Image.fromarray(pixels).save(jpeg, format="JPEG", quality=91)
        jpeg.seek(0)
        c.drawImage(ImageReader(jpeg), 10 * mm, 5 * mm, 20 * mm, 10 * mm)
    c.save()
    if with_image:
        with pikepdf.open(source, allow_overwriting_input=True) as pdf:
            pdf.pages.append(pdf.pages[0])
            pdf.save(source)
    original = source.read_bytes()
    with pikepdf.open(source) as pdf:
        source_images = [obj for obj in xobjects(pdf.pages[0].Resources) if obj.Subtype == "/Image"]
        expected = [(obj.Width, obj.Height, obj.read_raw_bytes()) for obj in source_images]
    output = tmp_path / "out"
    output.mkdir()
    run(output, "burger", [source], {})
    with pikepdf.open(output / "bat.pdf") as pdf:
        assert len(pdf.pages) == (4 if with_image else 3)
        assert sum(obj.get("/Subtype") == "/Image" for obj in pdf.objects) == len(expected)
        for page in pdf.pages:
            objects = list(xobjects(page.Resources))
            images = {obj.objgen: obj for obj in objects if obj.Subtype == "/Image"}.values()
            assert [(obj.Width, obj.Height, obj.read_raw_bytes()) for obj in images] == expected
            operators = [
                str(op)
                for obj in objects
                if obj.Subtype == "/Form"
                for _, op in pikepdf.parse_content_stream(obj)
            ]
            assert {"Tj", "c", "S", "K"} <= set(operators)
    with pdfium.PdfDocument(str(output / "bat.pdf")) as pdf:
        assert all("TEXTE SOURCE VECTORIEL" in p.get_textpage().get_text_range() for p in pdf)
    assert source.read_bytes() == original


@pytest.mark.parametrize("masked", [False, True])
def test_finishing_overlay_is_300_dpi_at_its_displayed_size(tmp_path, masked):
    snapshot = specification()
    finish_id = "varnish" if masked else "lamination"
    snapshot.variant.finish_ids = [finish_id]
    finish = next(f for f in snapshot.finishes if f.id == finish_id)
    finish.appearance = FinishAppearance(mode="area", color="#ff0000", alpha=0.4, gradient=True)
    files = artwork(tmp_path, snapshot)
    output = tmp_path / "out"
    output.mkdir()
    run(output, "burger", files, {"product_snapshot": snapshot.model_dump()})
    with pikepdf.open(output / "bat.pdf") as pdf:
        for page in list(pdf.pages)[:2]:
            matrix = pikepdf.Matrix()
            stack = []
            overlays = 0
            for args, op in pikepdf.parse_content_stream(page):
                if str(op) == "q":
                    stack.append(matrix)
                elif str(op) == "Q":
                    matrix = stack.pop()
                elif str(op) == "cm":
                    matrix = pikepdf.Matrix(*args) @ matrix
                elif str(op) == "Do":
                    obj = page.Resources.XObject[args[0]]
                    if obj.Subtype != "/Image":
                        continue
                    overlays += 1
                    a, b, c, d, _, _ = matrix.shorthand
                    assert int(obj.Width) * 72 / (a * a + b * b) ** 0.5 == pytest.approx(300, abs=1)
                    assert int(obj.Height) * 72 / (c * c + d * d) ** 0.5 == pytest.approx(
                        300, abs=1
                    )
                    alpha = pikepdf.PdfImage(obj.SMask).as_pil_image()
                    assert alpha.getextrema()[0] == 0
                    if masked:
                        assert 0 < alpha.getextrema()[1] <= 102
                    else:
                        assert alpha.getextrema()[1] == 102
            assert overlays == 2
            assert any(
                obj.get("/SnackpressRole") == "/Artwork"
                for obj in dict(page.Resources.XObject).values()
            )


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_native_placement_handles_crop_origin_rotation_and_user_unit(tmp_path, rotation):
    source = tmp_path / "offset.pdf"
    c = new_canvas(source, 120, 100)
    c.setFillColorRGB(0, 0, 1)
    c.rect(0, 0, 120 * mm, 100 * mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.rect(13 * mm, 23 * mm, 85 * mm, 55 * mm, fill=1, stroke=0)
    # Four asymmetric color patches prove orientation as well as centering.
    for color, x, y in [((1, 0, 0), 20, 30), ((0, 1, 0), 80, 30), ((1, 1, 0), 20, 65)]:
        c.setFillColorRGB(*color)
        c.rect(x * mm, y * mm, 5 * mm, 5 * mm, fill=1, stroke=0)
    c.save()
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        page.CropBox = pikepdf.Array([10 * mm, 20 * mm, 101 * mm, 81 * mm])
        page.TrimBox = pikepdf.Array([13 * mm, 23 * mm, 98 * mm, 78 * mm])
        page.Rotate = rotation
        page.UserUnit = 2
        pdf.save(source, min_version="1.6")
    output = tmp_path / "out"
    output.mkdir()
    run(output, "burger", [source], {})
    with pdfium.PdfDocument(str(source)) as pdf:
        native = np.array(pdf[0].render(scale=2).to_pil().convert("RGB"))
    with pdfium.PdfDocument(str(output / "bat.pdf")) as pdf:
        control = np.array(pdf[1].render(scale=2).to_pil().convert("RGB"))
        clean = np.array(pdf[0].render(scale=2).to_pil().convert("RGB"))
    # Locate the three flat-color patch centers and compare their normalized
    # geometry. This catches swaps, translation errors and inherited scaling.
    centers = []
    for image in (native, control):
        points = []
        for color in ((255, 0, 0), (0, 255, 0), (255, 255, 0)):
            rows, cols = np.where(np.all(image == color, axis=2))
            assert rows.size > 50
            points.append((cols.mean(), rows.mean()))
        points = np.array(points)
        centers.append((points - points[0]) / np.linalg.norm(points[1] - points[0]))
    assert centers[0] == pytest.approx(centers[1], abs=0.02)
    assert not np.any(np.all(clean == (0, 0, 255), axis=2))
