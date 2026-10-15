"""Generate our own synthetic card: no customer data, no third-party artwork."""

from pathlib import Path

import pikepdf
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PT = 72 / 25.4
pdf = pikepdf.Pdf.new()
regular = pdf.make_indirect(
    pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica
    )
)
bold = pdf.make_indirect(
    pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name("/Helvetica-Bold")
    )
)
for back in (False, True):
    page = pdf.add_blank_page(page_size=(91 * PT, 61 * PT))
    page.TrimBox = pikepdf.Array([3 * PT, 3 * PT, 88 * PT, 58 * PT])
    page.BleedBox = page.MediaBox
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=regular, F2=bold))
    w, h = 91 * PT, 61 * PT
    if not back:
        content = f"""q
0.05 0.04 0.11 0 k 0 0 {w} {h} re f
0.7 0.35 0.6 0.5 k
BT /F2 25 Tf 26 94 Td (studio) Tj 0 -27 Td (papier.) Tj ET
0.2 0.65 0.75 0.05 k 27 51 34 3 re f
0.7 0.35 0.6 0.5 k
BT /F1 6 Tf 27 29 Td (DESIGN GRAPHIQUE & BELLES IMPRESSIONS) Tj ET
Q"""
    else:
        content = f"""q
0.7 0.35 0.6 0.5 k 0 0 {w} {h} re f
0.05 0.04 0.11 0 k
BT /F2 12 Tf 27 112 Td (Faisons bonne impression.) Tj ET
BT /F1 7 Tf 27 77 Td (Camille Martin) Tj 0 -13 Td (Graphiste & amoureuse du papier) Tj ET
BT /F1 7 Tf 27 37 Td (bonjour@studio-papier.example) Tj ET
0.2 0.65 0.75 0.05 k 216 27 14 14 re f
Q"""
    page.Contents = pikepdf.Stream(pdf, content.encode("ascii"))
output = Path(__file__).resolve().parents[1] / "apps/web/public/exemple-carte.pdf"
output.parent.mkdir(parents=True, exist_ok=True)
pdf.save(output)

# Additional synthetic fixtures for the tool catalogue.
with pikepdf.open(output) as source:
    source.pages[0].contents_add(
        pikepdf.Stream(source, b"q 0 0 0 1 k BT /F1 8 Tf 150 140 Td (VERSION 2) Tj ET Q")
    )
    source.save(output.with_name("exemple-carte-v2.pdf"))


booklet = canvas.Canvas(str(output.with_name("exemple-livret.pdf")), pagesize=(148 * mm, 210 * mm))
for index in range(8):
    booklet.setFillColorRGB(0.09, 0.24, 0.21)
    booklet.setFont("Helvetica", 22)
    booklet.drawString(18 * mm, 175 * mm, "Le petit carnet")
    booklet.setFont("Helvetica", 70)
    booklet.drawString(18 * mm, 125 * mm, str(index + 1))
    booklet.setFont("Helvetica", 10)
    booklet.drawString(18 * mm, 20 * mm, "Exemple synthetique Snackpress - 8 pages")
    booklet.showPage()
booklet.save()

with pikepdf.open(output) as source:
    background = pikepdf.Pdf.new()
    background.pages.append(source.pages[0])
    background.save(output.with_name("exemple-fond.pdf"))
