from pathlib import Path

import pikepdf
from pydantic import BaseModel

from .geometry import Plan

PT = 72 / 25.4


class PageInfo(BaseModel):
    width: float
    height: float
    has_trim: bool
    available_bleed: float
    trim: list[float]


class DocumentInfo(BaseModel):
    pages: list[PageInfo]
    warnings: list[str]


def describe(pdf: pikepdf.Pdf) -> DocumentInfo:
    if pdf.is_encrypted:
        raise ValueError("PDF protégé : fournissez une copie sans protection.")
    if len(pdf.pages) not in (1, 2):
        raise ValueError("Importez un PDF de 1 page (recto) ou 2 pages (recto verso).")
    if pdf.Root.get("/AcroForm"):
        raise ValueError("Les formulaires et signatures ne sont pas pris en charge.")
    pages = []
    warnings = []
    for page in pdf.pages:
        if page.obj.get("/Annots"):
            raise ValueError("Les PDF contenant des annotations ne sont pas pris en charge.")
        if int(page.obj.get("/Rotate", 0)) % 360:
            raise ValueError("Rotation de page PDF non prise en charge : normalisez le PDF source.")
        if float(page.obj.get("/UserUnit", 1)) != 1:
            raise ValueError("Unités PDF non standard : normalisez le PDF source.")
        trim = [float(v) for v in page.trimbox]
        media = [float(v) for v in page.mediabox]
        crop = [float(v) for v in page.cropbox]
        bounds = [
            max(media[0], crop[0]),
            max(media[1], crop[1]),
            min(media[2], crop[2]),
            min(media[3], crop[3]),
        ]
        x, y, r, t = trim
        if not all(abs(v) < 1e7 for v in trim + bounds) or r <= x or t <= y:
            raise ValueError("Boîtes de page invalides.")
        bleed = min(x - bounds[0], y - bounds[1], bounds[2] - r, bounds[3] - t) / PT
        if bleed < -0.01:
            raise ValueError("La zone de coupe dépasse la zone visible du PDF.")
        if (r - x) / PT > 1200 or (t - y) / PT > 1200:
            raise ValueError("Le prototype limite les pages source à 1 200 mm par côté.")
        pages.append(
            PageInfo(
                width=(r - x) / PT,
                height=(t - y) / PT,
                has_trim="/TrimBox" in page.obj,
                available_bleed=max(0, bleed),
                trim=trim,
            )
        )
    if len(pages) == 2 and (
        abs(pages[0].width - pages[1].width) > 0.02 or abs(pages[0].height - pages[1].height) > 0.02
    ):
        raise ValueError("Les formats finis du recto et du verso sont différents.")
    if any(not p.has_trim for p in pages):
        warnings.append("TrimBox absente : confirmez le format proposé avant l’export.")
    warnings.append("Diagnostic géométrique uniquement ; aucune certification PDF/X.")
    return DocumentInfo(pages=pages, warnings=warnings)


def inspect(path: Path) -> DocumentInfo:
    try:
        with pikepdf.open(path) as pdf:
            return describe(pdf)
    except pikepdf.PasswordError as exc:
        raise ValueError("PDF protégé : fournissez une copie sans mot de passe.") from exc
    except pikepdf.PdfError as exc:
        raise ValueError("PDF illisible ou endommagé. Réexportez le document source.") from exc


def compose(source: Path, destination: Path, plan: Plan) -> None:
    with pikepdf.open(source) as pdf:
        info = describe(pdf)
        s = plan.settings
        for page in info.pages:
            if abs(page.width - s.trim_width) > 0.02 or abs(page.height - s.trim_height) > 0.02:
                raise ValueError(
                    "Le format fini doit correspondre au PDF : aucune mise à l’échelle."
                )
            if s.bleed > page.available_bleed + 0.01:
                raise ValueError("Fond perdu demandé indisponible dans le PDF source.")
            if not page.has_trim and not s.confirm_trim:
                raise ValueError("Confirmez le format fini : ce PDF ne contient pas de TrimBox.")
        source_count = len(pdf.pages)
        for index, placements in enumerate(
            [plan.front, plan.back] if source_count == 2 else [plan.front]
        ):
            src = pdf.pages[index]
            box = info.pages[index].trim
            # Clip and translate native objects at their original scale.
            form = src.as_form_xobject()
            b = s.bleed * PT
            form.BBox = pikepdf.Array([box[0] - b, box[1] - b, box[2] + b, box[3] + b])
            form.Matrix = pikepdf.Array([1, 0, 0, 1, 0, 0])
            sheet = pdf.add_blank_page(page_size=(s.sheet_width * PT, s.sheet_height * PT))
            name = sheet.add_resource(form, pikepdf.Name.XObject)
            commands = []
            for p in placements:
                x, y = p.x * PT, p.y * PT
                if p.rotation == 0:
                    matrix = (1, 0, 0, 1, x - box[0], y - box[1])
                else:
                    matrix = (0, 1, -1, 0, x + box[3], y - box[0])
                commands.append("q " + " ".join(f"{n:.8f}" for n in matrix) + f" cm {name} Do Q")
            commands.append("q 0 0 0 1 K 0.25 w")
            for mark in plan.marks:
                commands.append(
                    f"{mark.x1 * PT:.8f} {mark.y1 * PT:.8f} m "
                    f"{mark.x2 * PT:.8f} {mark.y2 * PT:.8f} l S"
                )
            commands.append("Q")
            sheet.contents_add(pikepdf.Stream(pdf, "\n".join(commands).encode("ascii")))
        for _ in range(source_count):
            del pdf.pages[0]
        # Keep output intents; clear stale conformance and page-tree metadata.
        if "/Metadata" in pdf.Root:
            del pdf.Root["/Metadata"]
        for key in (
            "/PageLabels",
            "/Outlines",
            "/OpenAction",
            "/Names",
            "/StructTreeRoot",
            "/MarkInfo",
        ):
            if key in pdf.Root:
                del pdf.Root[key]
        for key in list(pdf.docinfo.keys()):
            if "PDFX" in str(key).upper():
                del pdf.docinfo[key]
        pdf.save(destination)
