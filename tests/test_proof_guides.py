import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import proof_body_count
from reportlab.lib.units import mm
from snackpress_tools.common import new_canvas
from snackpress_tools.preview import render
from snackpress_tools.runner import run
from test_products import artwork, content, specification


@pytest.mark.parametrize("mode", ["classic", "product", "preview"])
@pytest.mark.parametrize("background", ["black", "#cc4c80"])
def test_print_guides_visible_and_registered_over_artwork(tmp_path, mode, background):
    source = tmp_path / "source.pdf"
    c = new_canvas(source, 91, 61)
    c.setFillColor(background)
    c.rect(0, 0, 91 * mm, 61 * mm, fill=1, stroke=0)
    c.save()
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.pages[0].TrimBox = pikepdf.Array([3 * mm, 3 * mm, 88 * mm, 58 * mm])
        pdf.save(source)
    original = source.read_bytes()
    settings = {"template_tool": "pizza", "template_settings": {"safety_left": 5}}
    files = [source]
    if mode != "classic":
        snapshot = specification()
        snapshot.variant.components[0].guides[0].settings["safety_left"] = 5
        # Revalidate from the model's full settings, as the API does.
        settings = {"product_snapshot": snapshot.model_dump()}
        files = [source, source]
    out = tmp_path / "out"
    out.mkdir()
    (render if mode == "preview" else run)(out, "burger", files, settings)
    path = out / "bat.pdf"
    text = content(path)
    for label in ("Coupe / format fini", "Fond perdu", "tranquillité"):
        assert label in text
    # Locate each guided control from the PDF placement operators, regardless
    # of how many artwork faces share the page.
    with pikepdf.open(path) as proof:
        controls = []
        for index, page in enumerate(proof.pages):
            placements = []
            matrix, stack = pikepdf.Matrix(), []
            for args, op in pikepdf.parse_content_stream(page):
                if str(op) == "q":
                    stack.append(matrix)
                elif str(op) == "Q":
                    matrix = stack.pop()
                elif str(op) == "cm":
                    matrix = pikepdf.Matrix(*args) @ matrix
                elif str(op) == "Do":
                    obj = page.Resources.XObject[args[0]]
                    if obj.get("/SnackpressRole") == "/Guide":
                        placements.append(matrix.shorthand)
            if placements:
                controls.append((index, placements))
        assert len(controls) == 1
        assert len(controls[0][1]) == len(files)
    with pdfium.PdfDocument(str(path)) as pdf:
        for index, placements in controls:
            pixels = np.asarray(pdf[index].render(scale=2).to_pil().convert("RGB"))
            for a, b, c, d, e, f in placements:
                for source_x, color in [
                    (0, (50, 101, 201)), (3, (201, 109, 77)), (8, (24, 61, 54))
                ]:
                    x = round((e + source_x * a * mm) * 2)
                    top = round((297 * mm - f - 40 * d * mm) * 2)
                    end = round((297 * mm - f - 15 * d * mm) * 2)
                    strip = pixels[top:end, max(0, x - 2) : x + 3].astype(int)
                    assert np.count_nonzero(np.all(abs(strip - color) < 25, axis=2)) > 10, (
                        mode,
                        background,
                        source_x,
                    )
    if mode != "classic":
        with pikepdf.open(out / "composant-1/visuel-0.pdf") as pdf:
            page = pdf.pages[0]
            assert [float(n) / mm for n in page.cropbox] == pytest.approx([0, 0, 91, 61])
            assert [float(n) / mm for n in page.trimbox] == pytest.approx([3, 3, 88, 58])
    assert source.read_bytes() == original


@pytest.mark.parametrize("product_id", ["brochure", "leaflet", "ticket"])
def test_print_guides_exist_without_a_pizza_template(tmp_path, product_id):
    snapshot = specification(product_id)
    files = artwork(tmp_path, snapshot)
    out = tmp_path / "out"
    out.mkdir()
    run(out, "burger", files, {"product_snapshot": snapshot.model_dump()})
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        for page in list(pdf)[: proof_body_count(out / "bat.pdf")]:
            text = page.get_textpage().get_text_range()
            if "Présentation" in text:
                assert "Légende des repères" not in text
                continue
            for label in ("Coupe / format fini", "Fond perdu", "tranquillité"):
                assert label in text
    if product_id == "leaflet":
        assert "Pliage" in content(out / "bat.pdf")
    if product_id == "ticket":
        assert "Perforation" in content(out / "bat.pdf")
