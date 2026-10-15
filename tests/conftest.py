from pathlib import Path

import pikepdf
import pytest
from snackpress_imposition.pdf import PT


def make_pdf(path: Path, pages=2, origin=(0, 0), trim=True, rotation=0):
    pdf = pikepdf.Pdf.new()
    font = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica
        )
    )
    x, y = origin
    for i in range(pages):
        page = pdf.add_blank_page(page_size=(91 * PT, 61 * PT))
        page.MediaBox = pikepdf.Array([x, y, x + 91 * PT, y + 61 * PT])
        if trim:
            page.TrimBox = pikepdf.Array([x + 3 * PT, y + 3 * PT, x + 88 * PT, y + 58 * PT])
        if rotation:
            page.Rotate = rotation
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
        face = "RECTO" if i == 0 else "VERSO"
        page.Contents = pikepdf.Stream(
            pdf,
            (
                f"q 1 0 0 1 {x} {y} cm "
                f"0.8 0.1 0 0.1 k 0 0 {91 * PT} {61 * PT} re f "
                "0 0 0 0 k BT /F1 12 Tf 20 125 Td (STUDIO PAPIER) Tj ET "
                f"BT /F1 8 Tf 20 25 Td ({face} - COIN BAS GAUCHE) Tj ET Q"
            ).encode(),
        )
    pdf.save(path)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.pdf"
    make_pdf(path)
    return path
