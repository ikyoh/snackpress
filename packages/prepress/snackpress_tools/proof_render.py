"""One ordered proof: finished presentation, guided composite, separated elements."""

from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory

import pikepdf
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .common import full_page_form, new_canvas, open_pdf, paginate_pdf, report
from .finish_appearance import simulate_finishes
from .proof_layout import draw_legend, header_footer


@dataclass
class ProofItem:
    source: Path
    source_page: int
    source_count: int
    label: str
    width: float
    height: float
    trim: tuple
    visual: bool
    guide: tuple | None
    guide_face: int
    legend: list
    native_guide: bool = True
    shape: dict = field(default_factory=dict)
    finish_styles: tuple = ()
    finish_masks: dict = field(default_factory=dict)
    mask_page_counts: dict = field(default_factory=dict)
    finish_page: int = 0
    finish_placements: tuple = ()
    only_finish: bool = False


def trim_pixels(item, image):
    x, y, w, h = item.trim
    return (
        round(x / item.width * image.width),
        round((item.height - y - h) / item.height * image.height),
        round((x + w) / item.width * image.width),
        round((item.height - y) / item.height * image.height),
    )


def finish_overlay(item, scale):
    """Only finishing simulations are rasterized, at 300 dpi on the BAT page."""
    dpi = 300 * scale
    size = (max(1, round(item.width * dpi / 25.4)), max(1, round(item.height * dpi / 25.4)))
    image = Image.new("RGBA", size)
    return simulate_finishes(
        image,
        item.finish_styles,
        item.finish_masks,
        item.finish_page,
        dpi,
        region=trim_pixels(item, image),
        mask_page_counts=item.mask_page_counts,
        finish_placements=item.finish_placements,
    )


def has_finish_simulation(finishes):
    return any(
        finish.appearance.mode != "none"
        and (finish.appearance.mode != "area" or finish.appearance.alpha > 0)
        for finish in finishes
    )


def canvas_size(item, clean):
    if clean:
        return item.trim[2:]
    return item.guide[1] if item.guide else (item.width, item.height)


def grid(items, width, height, clean):
    """Choose the grid that gives this set of page proportions the most display area."""
    candidates = []
    for cols in range(1, min(3, len(items)) + 1):
        rows = ceil(len(items) / cols)
        cw, ch = (width - (cols - 1) * 6) / cols, (height - (rows - 1) * 8) / rows
        area = sum(
            w * h * min(cw / w, (ch - 10) / h) ** 2
            for w, h in (canvas_size(item, clean) for item in items)
        )
        candidates.append((area, cols, cw, ch))
    return max(candidates)[1:]


def caption(c, text, x, y, width):
    size = 8
    while c.stringWidth(text, "Snack", size) > width * mm and len(text) > 4:
        text = text[:-2].rstrip("…") + "…"
    c.setFont("Snack", size)
    c.drawString(x * mm, y * mm, text)


def clip_finished(c, item, x, y, width, height):
    shape = item.shape.get("shape", "rectangle")
    clip = c.beginPath()
    if shape in {"circle", "ellipse"}:
        clip.ellipse(x * mm, y * mm, width * mm, height * mm)
    else:
        radius = (
            item.shape.get("corner_radius", 0) * width / item.trim[2] if shape == "rectangle" else 0
        )
        clip.roundRect(x * mm, y * mm, width * mm, height * mm, radius * mm)
    c.clipPath(clip, stroke=0, fill=0)


def render_proof(path, items, params, date, *, paginate=True, technical_sheet=None):
    c = new_canvas(path, 210, 297)
    placements = []
    artwork = []
    page_index = 0
    visuals = [item for item in items if item.visual]
    # Raw artwork only adds information when the composite simulates a finish.
    separated = [item for item in visuals if has_finish_simulation(item.finish_styles)]
    separated += [item for item in items if not item.visual]
    for item in visuals:
        for finish in item.finish_styles:
            if not finish.mask and has_finish_simulation((finish,)):
                separated.append(
                    replace(
                        item,
                        visual=False,
                        only_finish=True,
                        finish_styles=(finish,),
                        label=f"Finition : {finish.name} — {item.label}",
                    )
                )
    # Group every component globally, so separated elements never interrupt the
    # presentation or the composite controls of a product with several components.
    sections = [
        ("Présentation — visuels avec finitions", True, True, visuals),
        ("Contrôle — visuels avec finitions", False, True, visuals),
        ("Éléments séparés", False, False, separated),
    ]
    for section, clean, composite, entries in sections:
        chunk_size = 6 if composite else 1
        for offset in range(0, len(entries), chunk_size):
            batch = entries[offset : offset + chunk_size]
            legends = list(dict.fromkeys(entry for item in batch for entry in item.legend))
            guided = not clean and any(item.guide for item in batch)
            if not guided:
                legends = []
            bottom = 65 + max(0, (len(legends) + 1) // 2 - 2) * 5
            cols, cw, ch = grid(batch, 174, 249 - bottom, clean)
            header_footer(c, date)
            c.setFillColor(colors.black)
            c.setFont("SnackDisplay", 18)
            c.drawString(18 * mm, 267 * mm, params.title)
            c.setFont("Snack", 9)
            subtitle = section
            if clean:
                subtitle += " — format fini, sans repères"
            elif guided:
                subtitle += " — avec repères de gabarit"
            c.drawString(18 * mm, 259 * mm, subtitle)
            for slot, item in enumerate(batch):
                left = 18 + (slot % cols) * (cw + 6)
                top = 249 - (slot // cols) * (ch + 8)
                label = f"{item.label} — page {item.source_page + 1} / {item.source_count}"
                if item.guide and not clean:
                    with open_pdf(item.guide[0], max_pages=2) as guide:
                        if len(guide.pages) == 2:
                            label += " — " + ("Recto" if item.guide_face == 0 else "Verso")
                caption(c, label, left, top - 3, cw)
                bw, bh = canvas_size(item, clean)
                scale = min(cw / bw, (ch - 10) / bh)
                x = left + (cw - bw * scale) / 2
                y = top - ch + (ch - 10 - bh * scale) / 2
                ix = iy = 0
                iw, ih = item.width, item.height
                if clean:
                    ix, iy = -item.trim[0], -item.trim[1]
                if item.guide and not clean:
                    _, (gw, gh), (ox, oy, _, _) = item.guide
                    if abs(item.width - gw) > 1 or abs(item.height - gh) > 1:
                        ix, iy = ox, oy
                c.saveState()
                if clean:
                    clip_finished(c, item, x, y, bw * scale, bh * scale)
                if not item.only_finish:
                    # A public ReportLab form reserves the resource name. Its empty
                    # contents are replaced with the native PDF after layout.
                    name = f"Artwork{len(artwork)}"
                    c.beginForm(name, 0, 0, iw * mm, ih * mm)
                    c.endForm()
                    c.saveState()
                    c.translate((x + ix * scale) * mm, (y + iy * scale) * mm)
                    c.scale(scale, scale)
                    c.doForm(name)
                    c.restoreState()
                    artwork.append((page_index, name, item))
                if (composite or item.only_finish) and has_finish_simulation(item.finish_styles):
                    c.drawImage(
                        ImageReader(finish_overlay(item, scale)),
                        (x + ix * scale) * mm,
                        (y + iy * scale) * mm,
                        width=iw * scale * mm,
                        height=ih * scale * mm,
                        mask="auto",
                    )
                c.restoreState()
                if item.guide and not clean:
                    placements.append(
                        (
                            page_index,
                            item,
                            pikepdf.Rectangle(
                                x * mm, y * mm, (x + bw * scale) * mm, (y + bh * scale) * mm
                            ),
                            scale,
                        )
                    )
            if legends:
                draw_legend(c, legends, bottom)
            finishes = list(dict.fromkeys(f.name for item in batch for f in item.finish_styles))
            if composite and finishes:
                caption(c, "Finitions : " + ", ".join(finishes), 18, 43 if guided else 49, 174)
            c.setFont("Snack", 8)
            c.drawString(18 * mm, 38 * mm, "BAT DE PRÉSENTATION — COULEURS NON CONTRACTUELLES")
            c.drawString(
                18 * mm,
                31 * mm,
                "Format fini — fonds perdus masqués"
                if clean
                else "Visuels et fonds perdus avec repères"
                if guided
                else "Visuels sans gabarit",
            )
            c.drawString(18 * mm, 22 * mm, f"Client : {params.client[:75] or 'Non renseigné'}")
            c.showPage()
            page_index += 1
    c.save()
    embed_artwork(path, artwork)
    if placements:
        overlay_guides(path, placements)
    if technical_sheet is not None:
        append_technical_sheet(path, *technical_sheet, date)
    if paginate:
        paginate_pdf(path)


def append_technical_sheet(path, rows, note, date):
    """Append the technical report before numbering the entire BAT once."""
    with TemporaryDirectory(prefix="snackpress-bat-") as temporary:
        sheet = Path(temporary) / "fiche-technique.pdf"
        report(
            sheet,
            "Fiche technique du BAT",
            rows,
            note,
            branded_header=True,
            paginate=False,
            date=date,
            date_label="Date du BAT",
        )
        with pikepdf.open(path, allow_overwriting_input=True) as proof, pikepdf.open(sheet) as pdf:
            for page in pdf.pages:
                page.SnackpressSection = pikepdf.Name.TechnicalSheet
                proof.pages.append(page)
            proof.save(path)


def embed_artwork(path, placements):
    """Copy native PDF resources without resampling images or flattening paths/text."""
    with ExitStack() as stack, pikepdf.open(path, allow_overwriting_input=True) as proof:
        forms, sources = {}, {}
        version = max(proof.pdf_version, "1.4")
        for index, name, item in placements:
            page = proof.pages[index]
            key = (item.source, item.source_page)
            if key not in forms:
                # Keep each source open for the import pass so pikepdf can share
                # common fonts/images between faces instead of duplicating them.
                if item.source not in sources:
                    sources[item.source] = stack.enter_context(open_pdf(item.source, max_pages=200))
                source = sources[item.source]
                version = max(version, source.pdf_version)
                native = proof.copy_foreign(full_page_form(source.pages[item.source_page]))
                bounds = pikepdf.Rectangle(0, 0, item.width * mm, item.height * mm)
                # calc_form_xobject_placement accounts for CropBox origins and the
                # source form's rotation/UserUnit matrix before fitting the bounds.
                commands = page.calc_form_xobject_placement(
                    native, pikepdf.Name.Source, bounds, allow_shrink=True, allow_expand=True
                )
                form = proof.make_stream(b"q\n" + commands + b"\nQ\n")
                form.Type = pikepdf.Name.XObject
                form.Subtype = pikepdf.Name.Form
                form.BBox = pikepdf.Array(bounds)
                form.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Source=native))
                form.SnackpressRole = pikepdf.Name.Artwork
                forms[key] = form
            page.Resources.XObject[pikepdf.Name(f"/FormXob.{name}")] = forms[key]
        proof.save(path, min_version=version)


def overlay_guides(path, placements):
    from .burger import proof_strokes

    with pikepdf.open(path, allow_overwriting_input=True) as proof:
        forms = {}
        for index, item, rect, scale in placements:
            # Different grid cells need different stroke compensation. Cache only
            # identical placements; never mutate a shared form for another scale.
            key = (item.guide[0], item.guide_face, round(scale, 8))
            if key not in forms:
                with open_pdf(item.guide[0], max_pages=2) as source:
                    form = proof.copy_foreign(full_page_form(source.pages[item.guide_face]))
                form.SnackpressRole = pikepdf.Name.Guide
                if item.native_guide:
                    proof_strokes(form, scale)
                forms[key] = form
            page = proof.pages[index]
            blending = pikepdf.Dictionary(
                Type=pikepdf.Name.ExtGState,
                BM=pikepdf.Name.Normal if item.native_guide else pikepdf.Name.Multiply,
            )
            state_name = page.add_resource(blending, pikepdf.Name.ExtGState)
            name = page.add_resource(forms[key], pikepdf.Name.XObject)
            placement = page.calc_form_xobject_placement(
                forms[key], name, rect, allow_shrink=True, allow_expand=True
            )
            page.contents_add(b"q\n" + str(state_name).encode() + b" gs\n" + placement + b"\nQ\n")
        proof.save(path)
