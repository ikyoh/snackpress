import pikepdf
import pytest
from reportlab.lib.units import mm
from snackpress_tools.artwork_geometry import validate_page
from snackpress_tools.common import new_canvas
from snackpress_tools.runner import run


def document(path, width, height, *, trim=None, crop=None, bleedbox=None):
    c = new_canvas(path, width, height)
    c.setFillColorRGB(0.6, 0.2, 0.4)
    c.rect(0, 0, width * mm, height * mm, fill=1)
    c.save()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        for key, box in (("TrimBox", trim), ("CropBox", crop), ("BleedBox", bleedbox)):
            if box is not None:
                page.obj[f"/{key}"] = pikepdf.Array([n * mm for n in box])
        pdf.save(path)


@pytest.mark.parametrize("bleed", [0, 3, 5])
@pytest.mark.parametrize("crop_to_trim", [False, True])
def test_classic_bat_expects_finished_size_plus_bleed(tmp_path, bleed, crop_to_trim):
    source = tmp_path / "source.pdf"
    trim = [bleed, bleed, 800 + bleed, 2000 + bleed]
    document(
        source,
        800 + 2 * bleed,
        2000 + 2 * bleed,
        trim=trim if crop_to_trim else None,
        crop=trim if crop_to_trim else None,
    )
    original = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    result = run(
        out,
        "burger",
        [source],
        {
            "template_tool": "pizza",
            "template_settings": {"width": 800, "height": 2000, "bleed": bleed},
        },
    )
    assert result.metrics["Pages du BAT"] == 4
    with pikepdf.open(out / "sources-validees/source-0.pdf") as pdf:
        page = pdf.pages[0]
        assert [float(n) / mm for n in page.trimbox] == pytest.approx(trim)
        crop = [float(n) / mm for n in page.cropbox]
        assert crop[2] - crop[0] == pytest.approx(800 + 2 * bleed)
        assert crop[3] - crop[1] == pytest.approx(2000 + 2 * bleed)
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "width,height,trim,bleedbox",
    [
        (800, 2000, None, None),
        (803, 2003, None, None),
        (806, 2006, [2, 3, 802, 2003], None),
        (806, 2006, [3, 3, 803, 2003], [3, 3, 803, 2003]),
        (806, 2006, [3, 3, 800, 2000], None),
    ],
)
def test_missing_or_incorrect_bleed_is_rejected(tmp_path, width, height, trim, bleedbox):
    source = tmp_path / "source.pdf"
    document(source, width, height, trim=trim, bleedbox=bleedbox)
    with pikepdf.open(source) as pdf, pytest.raises(ValueError, match="806 × 2006"):
        validate_page(pdf.pages[0], 800, 2000, 3, "Visuel 1")
