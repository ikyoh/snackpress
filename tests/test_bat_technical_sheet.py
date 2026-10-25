"""One BAT download includes its complete technical sheet and continuous numbering."""

import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import make_pdf, proof_body_count
from reportlab.lib.units import mm
from snackpress_tools.catalog import Burger
from snackpress_tools.preview import render
from snackpress_tools.products import FinishAppearance
from snackpress_tools.runner import run
from test_products import artwork, specification


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("mode", ["classic", "catalog"])
@pytest.mark.parametrize("long_notes", [False, True])
def test_technical_sheet_is_appended_and_not_offered_separately(
    tmp_path, preview, mode, long_notes
):
    notes = "\n".join(f"Instruction de fabrication {i:03d}" for i in range(90 if long_notes else 1))
    settings = {"title": "BAT intégré", "client": "Atelier Test", "notes": notes}
    if mode == "catalog":
        snapshot = specification()
        snapshot.variant.finish_ids = ["varnish"]
        snapshot.finishes[0].appearance = FinishAppearance(mode="area", color="#ff0000", alpha=0.4)
        files = artwork(tmp_path, snapshot)
        settings["product_snapshot"] = snapshot.model_dump()
    else:
        files = [tmp_path / "source.pdf"]
        make_pdf(files[0], pages=1)
    originals = [p.read_bytes() for p in files]
    output = tmp_path / "out"
    output.mkdir()
    result = (render if preview else run)(output, "burger", files, settings)
    assert "fiche-technique.pdf" not in [a.name for a in result.artifacts]
    assert not (output / "fiche-technique.pdf").exists()
    assert (
        sum(a.media_type == "application/pdf" and a.label == "BAT A4" for a in result.artifacts)
        == 1
    )
    body = proof_body_count(output / "bat.pdf")
    assert body == (6 if mode == "catalog" else 2)
    with pikepdf.open(output / "bat.pdf") as pdf:
        total = len(pdf.pages)
        assert result.metrics["Pages du BAT"] == total
        assert result.artifacts[0].pages == total
        assert (total - body > 1) == long_notes
        for page in list(pdf.pages)[body:]:
            assert page.SnackpressSection == "/TechnicalSheet"
            assert [float(v) for v in page.mediabox] == pytest.approx([0, 0, 210 * mm, 297 * mm])
    with pdfium.PdfDocument(str(output / "bat.pdf")) as pdf:
        texts = [p.get_textpage().get_text_range() for p in pdf]
        assert "Fiche technique du BAT" in texts[body]
        assert all("Fiche technique du BAT" not in t for t in texts[:body])
        appendix = "\n".join(texts[body:])
        assert "Atelier Test" in appendix and "Commentaires" in appendix
        assert f"Instruction de fabrication {89 if long_notes else 0:03d}" in appendix
        if mode == "catalog":
            assert "Vernis sélectif" in appendix and "85" in appendix and "55" in appendix
        for index, page in enumerate(pdf, 1):
            footer = page.get_textpage().get_text_bounded(
                left=150 * mm, bottom=0, right=210 * mm, top=18 * mm
            )
            assert footer.strip() == f"Page {index} / {total}"
            assert "Date du BAT :" in texts[index - 1]
            assert "snackpress.app" in texts[index - 1]
    assert [p.read_bytes() for p in files] == originals


def test_explicit_proof_date_is_shared_by_the_technical_sheet(tmp_path):
    from snackpress_tools.burger import generate

    source = tmp_path / "source.pdf"
    make_pdf(source, pages=1)
    generate(tmp_path, [source], Burger(), date="01/02/2030")
    with pdfium.PdfDocument(str(tmp_path / "bat.pdf")) as pdf:
        assert all("Date du BAT : 01/02/2030" in p.get_textpage().get_text_range() for p in pdf)
