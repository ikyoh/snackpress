import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import proof_body_count, proof_body_pages
from PIL import Image
from reportlab.lib.units import mm
from snackpress_tools.common import new_canvas
from snackpress_tools.preview import render
from snackpress_tools.products import FinishAppearance
from snackpress_tools.runner import run
from test_burger import guide_forms
from test_products import artwork, specification


def source(path, color=None, *, mask=False):
    c = new_canvas(path, 91, 61)
    c.setFillColorRGB(0, 0, 1)
    c.rect(0, 0, 91 * mm, 61 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*(color or (1, 1, 1)))
    c.rect(3 * mm, 3 * mm, 85 * mm, 55 * mm, fill=1, stroke=0)
    if mask:
        c.setFillColorRGB(0, 0, 0)
        c.rect(3 * mm, 3 * mm, 42 * mm, 55 * mm, fill=1, stroke=0)
    c.save()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].TrimBox = pikepdf.Array([3 * mm, 3 * mm, 88 * mm, 58 * mm])
        pdf.save(path)
    return path


def images(page):
    result = []
    for obj in dict(page.Resources.XObject).values():
        if obj.Subtype != "/Image":
            continue
        image = pikepdf.PdfImage(obj).as_pil_image().convert("RGBA")
        if "/SMask" in obj:
            image.putalpha(pikepdf.PdfImage(obj.SMask).as_pil_image())
        result.append(Image.alpha_composite(Image.new("RGBA", image.size, "white"), image))
    return [image.convert("RGB") for image in result]


@pytest.mark.parametrize("preview", [False, True])
def test_card_composites_then_separated_elements_with_real_bleed_hidden(tmp_path, preview):
    snapshot = specification()
    snapshot.variant.finish_ids = ["varnish"]
    snapshot.finishes[0].appearance = FinishAppearance(mode="area", color="#ff0000", alpha=1)
    front = source(tmp_path / "front.pdf")
    back = source(tmp_path / "back.pdf", (1, 1, 0))
    mask = source(tmp_path / "mask.pdf", mask=True)
    # The card's finish mask covers both visual faces.
    with pikepdf.open(mask, allow_overwriting_input=True) as pdf:
        pdf.pages.append(pdf.pages[0])
        pdf.save(mask)
    files = [front, back, mask]
    originals = [file.read_bytes() for file in files]
    out = tmp_path / "out"
    out.mkdir()
    result = (render if preview else run)(
        out, "burger", files, {"product_snapshot": snapshot.model_dump()}
    )
    assert result.metrics["Pages du BAT"] == 7
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        texts = [page.get_textpage().get_text_range() for page in pdf][
            : proof_body_count(out / "bat.pdf")
        ]
    assert "Présentation" in texts[0] and "Recto" in texts[0] and "Verso" in texts[0]
    assert "Légende des repères" not in texts[0]
    assert "Contrôle" in texts[1] and "Recto" in texts[1] and "Verso" in texts[1]
    assert all("Éléments séparés" in text for text in texts[2:])
    assert "Recto" in texts[2] and "Verso" in texts[3]
    assert "Vernis sélectif" in texts[4] and "Vernis sélectif" in texts[5]
    with pikepdf.open(out / "bat.pdf") as pdf:
        assert not guide_forms(pdf.pages[0])
        assert all(guide_forms(page) for page in proof_body_pages(pdf)[1:])
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        clean, guided, raw = [np.array(pdf[i].render(scale=2).to_pil()) for i in (0, 1, 2)]
        assert not np.any(np.all(clean[:, :, :3] == (0, 0, 255), axis=2))
        assert np.any(np.all(guided[:, :, :3] == (0, 0, 255), axis=2))
        for pixels in (clean, guided):
            assert np.count_nonzero(np.all(pixels[:, :, :3] == (255, 0, 0), axis=2)) > 10_000
        # The separated artwork must not contain the red finishing simulation.
        assert not np.any(np.all(raw[:, :, :3] == (255, 0, 0), axis=2))
    assert [file.read_bytes() for file in files] == originals


def test_sections_span_all_components_and_paginate_long_documents(tmp_path):
    snapshot = specification("brochure")
    files = artwork(tmp_path, snapshot)
    out = tmp_path / "out"
    out.mkdir()
    result = run(out, "burger", files, {"product_snapshot": snapshot.model_dump()})
    assert proof_body_count(out / "bat.pdf") == 16
    assert result.metrics["Pages du BAT"] > 16
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        texts = [page.get_textpage().get_text_range() for page in pdf][
            : proof_body_count(out / "bat.pdf")
        ]
    assert all("Présentation" in text and "Légende des repères" not in text for text in texts[:2])
    assert "Couverture" in texts[0] and "Intérieur" in texts[0]
    assert all("Contrôle" in text for text in texts[2:4])
    assert all("Éléments séparés" in text for text in texts[4:])
    assert all("Légende des repères" in text for text in texts[2:])


def test_finish_without_mask_has_a_separated_control(tmp_path):
    snapshot = specification()
    snapshot.variant.finish_ids = ["lamination"]
    finish = next(f for f in snapshot.finishes if f.id == "lamination")
    finish.appearance = FinishAppearance(mode="path", color="#ff0000", dash_color="#0000ff")
    files = artwork(tmp_path, snapshot)
    out = tmp_path / "out"
    out.mkdir()
    run(out, "burger", files, {"product_snapshot": snapshot.model_dump()})
    with pikepdf.open(out / "bat.pdf") as pdf:
        assert len(proof_body_pages(pdf)) == 6
        for page in proof_body_pages(pdf)[-2:]:
            image = images(page)[0]
            assert image.getpixel((image.width // 2, image.height // 2)) == (255, 255, 255)
            pixels = np.array(image)
            assert np.any(np.all(pixels == (255, 0, 0), axis=2))
            assert np.any(np.all(pixels == (0, 0, 255), axis=2))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_presentation_uses_trimbox_without_a_template(tmp_path, rotation):
    visual = source(tmp_path / "source.pdf")
    with pikepdf.open(visual, allow_overwriting_input=True) as pdf:
        pdf.pages[0].Rotate = rotation
        pdf.save(visual)
    out = tmp_path / "out"
    out.mkdir()
    run(out, "burger", [visual], {})
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        clean, control = [np.array(pdf[i].render(scale=2).to_pil()) for i in (0, 1)]
        assert not np.any(np.all(clean[:, :, :3] == (0, 0, 255), axis=2))
        assert np.any(np.all(control[:, :, :3] == (0, 0, 255), axis=2))


@pytest.mark.parametrize("tool", ["pizza", "sushi"])
def test_round_product_hides_bleed_outside_the_cut_shape(tmp_path, tool):
    visual = tmp_path / "round.pdf"
    margin = 3
    size = 80 + 2 * margin
    c = new_canvas(visual, size, size)
    c.setFillColorRGB(0, 0, 1)
    c.rect(0, 0, size * mm, size * mm, fill=1, stroke=0)
    c.setFillColorRGB(0, 1, 0)
    c.rect(margin * mm, margin * mm, 80 * mm, 80 * mm, fill=1, stroke=0)
    c.save()
    out = tmp_path / "out"
    out.mkdir()
    run(
        out,
        "burger",
        [visual],
        {
            "template_tool": tool,
            "template_settings": {"shape": "circle", "width": 80, "height": 80, "bleed": margin},
        },
    )
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        image = pdf[0].render(scale=2).to_pil().convert("RGB")

        def pixel(x, y):
            return image.getpixel((round(x * mm * 2), round((297 - y) * mm * 2)))

        assert pixel(105, 152) == (0, 255, 0)
        assert pixel(20, 237) == (255, 255, 255)
