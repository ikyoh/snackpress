import json

import pikepdf
import pypdfium2 as pdfium
import pytest
from snackpress_tools.catalog import Fortune
from snackpress_tools.runner import run

PT = 72 / 25.4


def artwork(path, *, trim=True, origin=(0, 0), cropped=False):
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(91 * PT, 61 * PT))
    x, y = origin
    page.MediaBox = [x, y, x + 91 * PT, y + 61 * PT]
    page.BleedBox = page.MediaBox
    box = [x + 3 * PT, y + 3 * PT, x + 88 * PT, y + 58 * PT]
    if trim:
        page.TrimBox = box
    if cropped:
        page.CropBox = box
    page.Contents = pdf.make_stream(
        (
            f"q 1 0 0 1 {x} {y} cm "
            f"1 0 0 rg 0 0 {91 * PT} {61 * PT} re f "
            f"0 0 1 rg {3 * PT} {3 * PT} {85 * PT} {55 * PT} re f Q"
        ).encode()
    )
    pdf.save(path)


@pytest.mark.parametrize(
    "trim,cropped,origin",
    [
        (False, False, (0, 0)),
        (True, False, (17, 29)),
        (True, True, (17, 29)),
    ],
)
def test_full_artwork_bleed_is_preserved_without_rescaling(tmp_path, trim, cropped, origin):
    source = tmp_path / "background.pdf"
    artwork(source, trim=trim, cropped=cropped, origin=origin)
    run(tmp_path, "fortune-cookie", [source], {"count": 2, "bleed": 3})
    with pikepdf.open(tmp_path / "serie.pdf") as pdf:
        assert len(pdf.pages) == 2
        assert list(map(float, pdf.pages[0].MediaBox)) == pytest.approx([0, 0, 91 * PT, 61 * PT])
        assert list(map(float, pdf.pages[0].TrimBox)) == pytest.approx(
            [3 * PT, 3 * PT, 88 * PT, 58 * PT]
        )
        assert pdf.pages[0].BleedBox == pdf.pages[0].MediaBox
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as pdf:
        page = pdf[0]
        bitmap = page.render(scale=4, rev_byteorder=True)
        image = bitmap.to_pil().convert("RGB")
        assert image.getpixel((round(PT * 4), round(PT * 4))) == (255, 0, 0)
        assert image.getpixel((round(4 * PT * 4), round(4 * PT * 4))) == (0, 0, 255)
        text = page.get_textpage()
        first = text.get_text_range().index("SP-0001")
        left, _, _, _ = text.get_charbox(first)
        assert left / PT == pytest.approx(9, abs=0.5)  # 6 mm from trim + 3 mm bleed.
        bitmap.close()


def test_each_imposed_pose_keeps_bleed_and_the_gap_stays_clear(tmp_path):
    source = tmp_path / "background.pdf"
    artwork(source, trim=False)
    result = run(
        tmp_path,
        "fortune-cookie",
        [source],
        {
            "count": 4,
            "bleed": 3,
            "tickets_per_book": 1,
            "layer_template": {"sheet_width": 210, "sheet_height": 150, "margin": 10, "gap": 8},
        },
    )
    assert result.metrics["Poses"] == 4
    with pdfium.PdfDocument(str(tmp_path / "imposition.pdf")) as pdf:
        bitmap = pdf[0].render(scale=4, rev_byteorder=True)
        image = bitmap.to_pil().convert("RGB")

        def pixel(x, y):
            return image.getpixel((round(x * PT * 4), round((150 - y) * PT * 4)))

        for x, y in [(16, 79), (109, 79), (16, 16), (109, 16)]:
            assert pixel(x - 1, y + 20) == (255, 0, 0)
            assert pixel(x + 1, y + 20) == (0, 0, 255)
        assert pixel(105, 100) == (255, 255, 255)
        bitmap.close()


def test_insufficient_or_incompatible_bleed_reports_the_expected_formats(tmp_path):
    source = tmp_path / "background.pdf"
    artwork(source)
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.pages[0].BleedBox = pdf.pages[0].TrimBox
        pdf.save(source)
    with pytest.raises(ValueError, match="fond perdu de 3 mm"):
        run(tmp_path, "fortune-cookie", [source], {"count": 1, "bleed": 3})
    run(tmp_path, "fortune-cookie", [source], {"count": 1, "bleed": 0})
    with pikepdf.open(tmp_path / "serie.pdf") as pdf:
        assert float(pdf.pages[0].MediaBox[2]) / PT == pytest.approx(85)
    with pytest.raises(ValueError, match="format fini attendu 80 × 50 mm"):
        run(tmp_path, "fortune-cookie", [source], {"width": 80, "height": 50, "bleed": 3})


def test_thousand_tickets_remain_in_sequence_after_imposition(tmp_path):
    result = run(
        tmp_path,
        "fortune-cookie",
        [],
        {
            "count": 1000,
            "tickets_per_book": 25,
            "layer_template": {"sheet_width": 210, "sheet_height": 150, "margin": 10, "gap": 6},
        },
    )
    assert result.metrics["Billets"] == 1000
    assert result.metrics["Souches"] == 40
    assert result.metrics["Feuilles à tirer"] == 250
    with pikepdf.open(tmp_path / "serie.pdf") as pdf:
        assert len(pdf.pages) == 1000
    manifest = json.loads((tmp_path / "plan-souches.json").read_text())
    gathered = [row[pose] for pose in range(4) for row in manifest["sheets"] if row[pose]]
    assert gathered == [f"SP-{index:04d}" for index in range(1, 1001)]


def test_pizza_supplies_the_bleed_and_legacy_codes_are_dropped():
    params = Fortune(bleed=3, pizza_template={"bleed": 4}, code="code128", payload="{n}")
    assert params.bleed == 4
    assert not {"code", "payload"}.intersection(params.model_dump())
    assert Fortune(count=1000).count == 1000
    with pytest.raises(ValueError):
        Fortune(count=1001)


@pytest.mark.parametrize("template", ["invalid", [1]])
def test_invalid_template_is_a_validation_error(template):
    with pytest.raises(ValueError):
        Fortune(pizza_template=template)
