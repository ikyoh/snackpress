import pikepdf
import pypdfium2 as pdfium
import pytest
from reportlab.lib.units import mm
from snackpress_tools.common import report
from snackpress_tools.runner import run


def assert_display_title_is_black(path, size):
    with pikepdf.open(path) as pdf:
        page = pdf.pages[0]
        font, font_size, color = None, None, (0, 0, 0)
        found = False
        for operands, operator in pikepdf.parse_content_stream(page):
            if str(operator) == "rg":
                color = tuple(float(n) for n in operands)
            elif str(operator) == "Tf":
                font = str(page.Resources.Font[operands[0]].BaseFont)
                font_size = float(operands[1])
            elif (
                str(operator) in {"Tj", "TJ"} and font_size == size and "LilitaOne" in (font or "")
            ):
                assert color == (0, 0, 0)
                found = True
        assert found, "Le titre doit utiliser la police Lilita One du logo."


def assert_page_totals(path):
    with pdfium.PdfDocument(str(path)) as pdf:
        for index, page in enumerate(pdf, 1):
            footer = page.get_textpage().get_text_bounded(
                left=150 * mm, bottom=0, right=210 * mm, top=18 * mm
            )
            assert footer.strip() == f"Page {index} / {len(pdf)}"
            bitmap = page.render(scale=1)
            try:
                image = bitmap.to_pil()
                crop = image.crop(
                    (int(150 * mm), image.height - int(18 * mm), image.width, image.height)
                )
                assert crop.convert("L").getextrema()[0] < 100, "La pagination doit être visible."
            finally:
                bitmap.close()
        return len(pdf)


@pytest.mark.parametrize("branded", [False, True])
@pytest.mark.parametrize("rows", [0, 120])
def test_report_titles_and_single_or_multiple_page_totals(tmp_path, branded, rows):
    path = tmp_path / "rapport.pdf"
    report(
        path,
        "Rapport de contrôle",
        [(f"Contrôle {i}", "Résultat de l’inspection") for i in range(rows)],
        branded_header=branded,
    )
    assert_display_title_is_black(path, 22)
    count = assert_page_totals(path)
    assert (count > 1) == bool(rows)


def test_bat_title_and_page_totals_preserve_pdf_links(tmp_path, source):
    run(tmp_path, "burger", [source], {})
    path = tmp_path / "bat.pdf"
    assert_display_title_is_black(path, 18)
    # Two faces: one presentation, one guided composite and two separated pages.
    assert assert_page_totals(path) == 4
    with pikepdf.open(path) as pdf:
        assert all(
            any(a.get("/A", {}).get("/URI") == "https://snackpress.app" for a in page.Annots)
            for page in pdf.pages
        )
