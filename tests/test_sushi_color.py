import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from reportlab.lib.units import mm
from snackpress_tools.catalog import Sushi
from snackpress_tools.common import new_canvas
from snackpress_tools.runner import run


@pytest.mark.parametrize("imported", [False, True])
@pytest.mark.parametrize("cmyk", [(100, 0, 100, 0), (12.5, 40, 65, 20), (0, 0, 0, 100)])
def test_cut_colour_matches_requested_cmyk_and_stays_a_spot(tmp_path, imported, cmyk):
    # Compare the rendered spot against an independent DeviceCMYK reference.
    reference = tmp_path / "reference.pdf"
    canvas = new_canvas(reference, 100, 80)
    canvas.setStrokeColorCMYK(*(value / 100 for value in cmyk))
    canvas.setLineWidth(mm)
    canvas.rect(10 * mm, 10 * mm, 80 * mm, 60 * mm)
    canvas.save()
    files = []
    if imported:
        source = tmp_path / "source.pdf"
        with pikepdf.Pdf.new() as pdf:
            page = pdf.add_blank_page(page_size=(100 * mm, 80 * mm))
            page.TrimBox = pikepdf.Array([10 * mm, 10 * mm, 90 * mm, 70 * mm])
            pdf.save(source)
        files = [source]
    settings = dict(zip(("cut_cyan", "cut_magenta", "cut_yellow", "cut_black"), cmyk))
    run(
        tmp_path,
        "sushi",
        files,
        {
            **settings,
            "shape": "rectangle",
            "width": 80,
            "height": 60,
            "bleed": 10,
            "cut_name": "CouleurAtelier",
            "cut_width": 1,
        },
    )
    target = tmp_path / "contours.pdf"
    with pikepdf.open(target) as pdf:
        page = pdf.pages[0]
        spaces = [space for _, space in page.Resources.ColorSpace.items()]
        assert len(spaces) == 1
        assert str(spaces[0][0]) == "/Separation"
        assert str(spaces[0][1]) == "/CouleurAtelier"
        assert str(spaces[0][2]) == "/DeviceCMYK"
        assert any(state.OP for _, state in page.Resources.ExtGState.items())
        assert "/XObject" not in page.Resources
        if imported:
            assert list(map(float, spaces[0][3].C1)) == pytest.approx([v / 100 for v in cmyk])
    with pdfium.PdfDocument(reference) as expected, pdfium.PdfDocument(target) as actual:
        first, second = expected[0].render(scale=2), actual[0].render(scale=2)
        a, b = np.array(first.to_pil()), np.array(second.to_pil())
        assert np.any(b < 200)
        assert np.abs(a.astype(float) - b.astype(float)).mean() < 0.1
        first.close()
        second.close()


@pytest.mark.parametrize("channel", ["cut_cyan", "cut_magenta", "cut_yellow", "cut_black"])
@pytest.mark.parametrize("value", [-0.1, 100.1, float("nan"), float("inf")])
def test_cut_cmyk_rejects_invalid_percentages(channel, value):
    with pytest.raises(ValueError):
        Sushi.model_validate({channel: value})


def test_old_sushi_settings_keep_magenta_by_default():
    assert Sushi.model_validate({"shape": "rectangle"}).cut_cmyk == (0, 1, 0, 0)
