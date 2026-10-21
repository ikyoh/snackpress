import json
from contextlib import contextmanager
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pikepdf
import pypdfium2 as pdfium
import reportlab
from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .catalog import Artifact

Image.MAX_IMAGE_PIXELS = 20_000_000
INK = colors.HexColor("#183d36")
CORAL = colors.HexColor("#c96d4d")


@lru_cache
def fonts():
    folder = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("Snack", str(folder / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("SnackBold", str(folder / "VeraBd.ttf")))
    display = Path(__file__).parent / "assets" / "fonts" / "LilitaOne-Regular.ttf"
    pdfmetrics.registerFont(TTFont("SnackDisplay", str(display)))


def new_canvas(path: Path, width: float, height: float):
    fonts()
    c = canvas.Canvas(str(path), pagesize=(width * mm, height * mm), pageCompression=1)
    c.setTitle(f"Snackpress - {path.stem}")
    c.setAuthor("Snackpress")
    c.setFont("Snack", 10)
    return c


def paginate_pdf(path: Path):
    """Add document-wide page totals after layout and component assembly are complete."""
    fonts()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pageCompression=1)
        for index, page in enumerate(pdf.pages, 1):
            width, height = float(page.mediabox[2]), float(page.mediabox[3])
            c.setPageSize((width, height))
            c.setFont("Snack", 8)
            c.setFillColor(colors.black)
            c.drawRightString(width - 18 * mm, 11 * mm, f"Page {index} / {len(pdf.pages)}")
            c.showPage()
        c.save()
        buffer.seek(0)
        with pikepdf.open(buffer) as numbering:
            for page, footer in zip(pdf.pages, numbering.pages, strict=True):
                names = {
                    name: page.add_resource(pdf.copy_foreign(font), pikepdf.Name.Font)
                    for name, font in footer.Resources.Font.items()
                }
                commands = []
                for operands, operator in pikepdf.parse_content_stream(footer):
                    if str(operator) == "Tf":
                        operands = [names[str(operands[0])], *operands[1:]]
                    commands.append((operands, operator))
                # Inline the text so guides and artwork keep their existing form structure.
                page.contents_add(b"q\n" + pikepdf.unparse_content_stream(commands) + b"\nQ\n")
        pdf.save(path)


def report(path: Path, title: str, rows, note="", *, branded_header=False):
    fonts()
    style = ParagraphStyle(
        "body",
        fontName="Snack",
        fontSize=9,
        leading=14,
        textColor=colors.black if branded_header else INK,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    heading = ParagraphStyle(
        "title",
        parent=style,
        fontName="SnackDisplay",
        textColor=colors.black,
        fontSize=22,
        leading=27,
        spaceAfter=18,
    )
    doc = SimpleDocTemplate(
        str(path),
        pagesize=(210 * mm, 297 * mm),
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=(30 if branded_header else 20) * mm,
        bottomMargin=20 * mm,
        title=title,
        author="Snackpress",
    )
    story = (
        []
        if branded_header
        else [
            Paragraph("SNACKPRESS / ATELIER PRÉPRESSE", style),
            Spacer(1, 12),
        ]
    )
    story.append(Paragraph(escape(title), heading))
    if note:
        story += [Paragraph(escape(note), style), Spacer(1, 16)]
    data = [
        [Paragraph(escape(str(k)), style), Paragraph(escape(str(v)).replace("\n", "<br/>"), style)]
        for k, v in rows
    ]
    if data:
        table = Table(data, colWidths=[52 * mm, 122 * mm], hAlign="LEFT", splitInRow=1)
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce2d6")),
                    ("TOPPADDING", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(table)

    if branded_header:
        from .proof_layout import header_footer, proof_date

        date = proof_date()

    def footer(c, doc):
        if branded_header:
            header_footer(c, date, date_label="Date du rapport")
            return
        c.setFont("Snack", 8)
        c.setFillColor(INK)
        c.drawString(
            18 * mm, 11 * mm, "Snackpress — document technique / vérifier avant fabrication"
        )

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    paginate_pdf(path)


def artifact(path: Path, label: str) -> Artifact:
    mime = {".pdf": "application/pdf", ".png": "image/png", ".json": "application/json"}
    pages = None
    if path.suffix == ".pdf":
        with pikepdf.open(path) as pdf:
            pages = len(pdf.pages)
    return Artifact(name=path.name, label=label, media_type=mime[path.suffix], pages=pages)


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@contextmanager
def open_pdf(path: Path, max_pages=80):
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError as exc:
        raise ValueError("PDF chiffré : fournissez une copie sans protection.") from exc
    except pikepdf.PdfError as exc:
        raise ValueError("PDF illisible : réexportez le document source.") from exc
    try:
        if pdf.is_encrypted:
            raise ValueError("Les PDF chiffrés ne sont pas pris en charge.")
        if not 1 <= len(pdf.pages) <= max_pages:
            raise ValueError(f"Le document doit contenir de 1 à {max_pages} pages.")
        for page in pdf.pages:
            box = [float(v) for v in page.mediabox]
            if not all(abs(v) < 1e7 for v in box) or box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError("Une boîte de page est invalide.")
        yield pdf
    finally:
        pdf.close()


def dimensions(page):
    rotation = int(page.obj.get("/Rotate", 0)) % 360
    b = page.cropbox
    unit = float(page.obj.get("/UserUnit", 1))
    if not 0 < unit <= 100:
        raise ValueError("Unité de page hors limites.")
    w, h = float(b[2] - b[0]) * unit / mm, float(b[3] - b[1]) * unit / mm
    return (h, w) if rotation in (90, 270) else (w, h)


def full_page_form(page):
    # pikepdf defaults to TrimBox, which clips bleed and rescales guide geometry.
    form = page.as_form_xobject()
    form.BBox = pikepdf.Array(page.cropbox)
    return form


def render_page(path: Path, index: int, dpi=96, max_pixels=20_000_000):
    with pdfium.PdfDocument(str(path)) as doc:
        page = doc[index]
        w, h = page.get_size()
        scale = dpi / 72
        if w * h * scale * scale > max_pixels:
            raise ValueError("Rendu trop grand : diminuez la résolution ou le format source.")
        bitmap = page.render(scale=scale, rev_byteorder=True, draw_annots=False)
        try:
            return bitmap.to_pil().convert("RGB").copy(), (w / mm, h / mm)
        finally:
            bitmap.close()
            page.close()


def load_image(path: Path):
    try:
        with Image.open(path) as src:
            if src.width * src.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("Image trop grande : 20 millions de pixels maximum.")
            img = ImageOps.exif_transpose(src).convert("RGBA")
            white = Image.new("RGBA", img.size, "white")
            return Image.alpha_composite(white, img).convert("RGB")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Image trop grande : 20 millions de pixels maximum.") from exc
    except OSError as exc:
        raise ValueError("Image illisible. Utilisez une image PNG ou JPEG.") from exc


def page_selection(value: str, count: int) -> list[int]:
    result = []
    try:
        for part in value.split(","):
            bounds = [int(x.strip()) for x in part.strip().split("-")]
            if len(bounds) == 1:
                result.append(bounds[0] - 1)
            elif len(bounds) == 2 and bounds[0] <= bounds[1] and bounds[1] - bounds[0] < 200:
                result.extend(range(bounds[0] - 1, bounds[1]))
            else:
                raise ValueError
    except ValueError as exc:
        raise ValueError("Pages invalides. Exemple : 1-4, 8, 6.") from exc
    if not result or len(result) > 200 or any(p < 0 or p >= count for p in result):
        raise ValueError("Une page demandée n’existe pas, ou plus de 200 pages sont sélectionnées.")
    return result
