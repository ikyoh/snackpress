"""Mixed-size native PDF imposition using several bounded MaxRects searches."""

from contextlib import ExitStack
from dataclasses import asdict, dataclass
from math import isfinite

import pikepdf
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .catalog import GranolaItem, ToolResult
from .common import artifact, load_image, new_canvas, open_pdf, write_json

EPS = 1e-7


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self):
        return self.x + self.width

    @property
    def top(self):
        return self.y + self.height

    def contains(self, other):
        return (
            self.x <= other.x + EPS
            and self.y <= other.y + EPS
            and self.right >= other.right - EPS
            and self.top >= other.top - EPS
        )


@dataclass(frozen=True)
class Pose:
    file: int
    copy: int
    x: float
    y: float
    width: float
    height: float
    rotation: int


def split_free(free, used):
    """Split every intersecting free rectangle, then remove contained rectangles."""
    fragments = []
    for rect in free:
        if (
            used.x >= rect.right - EPS
            or used.right <= rect.x + EPS
            or used.y >= rect.top - EPS
            or used.top <= rect.y + EPS
        ):
            fragments.append(rect)
            continue
        if used.x > rect.x + EPS:
            fragments.append(Rect(rect.x, rect.y, used.x - rect.x, rect.height))
        if used.right < rect.right - EPS:
            fragments.append(Rect(used.right, rect.y, rect.right - used.right, rect.height))
        if used.y > rect.y + EPS:
            fragments.append(Rect(rect.x, rect.y, rect.width, used.y - rect.y))
        if used.top < rect.top - EPS:
            fragments.append(Rect(rect.x, used.top, rect.width, rect.top - used.top))
    unique = list(dict.fromkeys(fragments))
    return [
        r
        for i, r in enumerate(unique)
        if not any(i != j and other.contains(r) for j, other in enumerate(unique))
    ]


def pack(sizes, items, params):
    width = params.sheet_width - 2 * params.margin
    height = params.sheet_height - 2 * params.margin
    for index, (w, h) in enumerate(sizes):
        if not (w <= width + EPS and h <= height + EPS) and not (
            params.rotation == "auto" and h <= width + EPS and w <= height + EPS
        ):
            raise ValueError(
                f"Fichier {index + 1} : {w:g} × {h:g} mm ne tient pas dans la zone "
                f"imprimable de {width:g} × {height:g} mm. Agrandissez la planche "
                "ou réduisez la marge (ou la largeur de l’image)."
            )
    orders = [
        sorted(range(len(sizes)), key=lambda i: (-sizes[i][0] * sizes[i][1], i)),
        sorted(range(len(sizes)), key=lambda i: (-max(sizes[i]), -min(sizes[i]), i)),
        sorted(range(len(sizes)), key=lambda i: (-sum(sizes[i]), i)),
    ]
    best = None
    for order in dict.fromkeys(tuple(order) for order in orders):
        for scoring in ("short", "area"):
            sheets, spaces = [], []
            for index in order:
                w, h = sizes[index]
                for copy in range(items[index].quantity):
                    selected = None
                    for sheet_index, free in enumerate(spaces):
                        for rect in free:
                            orientations = [(w, h, 0)]
                            if params.rotation == "auto" and abs(w - h) > EPS:
                                orientations.append((h, w, 90))
                            for pw, ph, rotation in orientations:
                                rw, rh = pw + params.gap, ph + params.gap
                                if rw > rect.width + EPS or rh > rect.height + EPS:
                                    continue
                                short = min(rect.width - rw, rect.height - rh)
                                area = rect.width * rect.height - rw * rh
                                score = (
                                    sheet_index,
                                    short if scoring == "short" else area,
                                    area if scoring == "short" else short,
                                    rect.y,
                                    rect.x,
                                    rotation,
                                )
                                if selected is None or score < selected[0]:
                                    selected = (score, sheet_index, rect, pw, ph, rotation)
                        # First-fit decreasing: fill existing sheets before opening another.
                        if selected is not None:
                            break
                    if selected is None:
                        sheet_index = len(sheets)
                        # More than 200 sheets cannot beat an already valid solution.
                        if sheet_index >= 200:
                            break
                        spaces.append([Rect(0, 0, width + params.gap, height + params.gap)])
                        sheets.append([])
                        orientations = [(w, h, 0)]
                        if params.rotation == "auto":
                            orientations.append((h, w, 90))
                        pw, ph, rotation = min(
                            (
                                o
                                for o in orientations
                                if o[0] <= width + EPS and o[1] <= height + EPS
                            ),
                            key=lambda o: (min(width - o[0], height - o[1]), o[1], o[2]),
                        )
                        rect = spaces[-1][0]
                    else:
                        _, sheet_index, rect, pw, ph, rotation = selected
                    sheets[sheet_index].append(
                        Pose(
                            index,
                            copy + 1,
                            rect.x + params.margin,
                            rect.y + params.margin,
                            pw,
                            ph,
                            rotation,
                        )
                    )
                    spaces[sheet_index] = split_free(
                        spaces[sheet_index], Rect(rect.x, rect.y, pw + params.gap, ph + params.gap)
                    )
                else:
                    continue
                break
            else:
                # Fewer sheets first, then leave the largest possible unused final area.
                score = (
                    len(sheets),
                    sum(p.width * p.height for p in sheets[-1]),
                    sum(max(p.y + p.height for p in sheet) for sheet in sheets),
                )
                if best is None or score < best[0]:
                    best = score, sheets
    if best is None:
        raise ValueError("Le travail dépasse 200 planches. Réduisez les quantités.")
    return best[1]


def page_geometry(page):
    unit = float(page.obj.get("/UserUnit", 1))
    rotation = int(page.obj.get("/Rotate", 0)) % 360
    media, crop = list(map(float, page.mediabox)), list(map(float, page.cropbox))
    x0, y0 = max(media[0], crop[0]), max(media[1], crop[1])
    x1, y1 = min(media[2], crop[2]), min(media[3], crop[3])
    if (
        not all(isfinite(v) and abs(v) < 1e7 for v in [*media, *crop, unit])
        or not 0 < unit <= 100
        or x1 <= x0
        or y1 <= y0
        or rotation % 90
    ):
        raise ValueError("Boîte, rotation ou unité de page PDF invalide.")
    if page.obj.get("/Annots"):
        raise ValueError("Aplatissez les annotations du PDF avant l’imposition.")
    w, h = (x1 - x0) * unit / mm, (y1 - y0) * unit / mm
    matrices = {
        0: (unit, 0, 0, unit, -x0 * unit, -y0 * unit),
        90: (0, -unit, unit, 0, -y0 * unit, x1 * unit),
        180: (-unit, 0, 0, -unit, x1 * unit, y1 * unit),
        270: (0, unit, -unit, 0, y1 * unit, -x0 * unit),
    }
    return ((h, w) if rotation in (90, 270) else (w, h), [x0, y0, x1, y1], matrices[rotation])


def transform(outer, inner):
    a, b, c, d, e, f = outer
    aa, bb, cc, dd, ee, ff = inner
    return (
        a * aa + c * bb,
        b * aa + d * bb,
        a * cc + c * dd,
        b * cc + d * dd,
        a * ee + c * ff + e,
        b * ee + d * ff + f,
    )


def impose(folder, files, params, *, preview=False):
    items = params.items or [GranolaItem() for _ in files]
    if len(items) != len(files):
        raise ValueError("Renseignez une quantité pour chaque fichier importé.")
    out = pikepdf.Pdf.new()
    forms, sizes, sources = [], [], []
    with ExitStack() as stack:
        for index, (path, item) in enumerate(zip(files, items, strict=True)):
            source = path
            if path.suffix != ".pdf":
                if item.page != 1:
                    raise ValueError(f"Fichier {index + 1} : une image contient une seule page.")
                image = load_image(path)
                height = item.image_width * image.height / image.width
                if height > 1200:
                    raise ValueError(f"Image {index + 1} : la hauteur dépasse 1 200 mm.")
                source = folder / f"image-{index}.pdf"
                c = new_canvas(source, item.image_width, height)
                c.drawImage(ImageReader(image), 0, 0, item.image_width * mm, height * mm)
                c.showPage()
                c.save()
            pdf = stack.enter_context(open_pdf(source))
            if pdf.Root.get("/AcroForm"):
                raise ValueError("Aplatissez les formulaires et signatures avant l’imposition.")
            if item.page > len(pdf.pages):
                raise ValueError(f"Fichier {index + 1} : la page {item.page} n’existe pas.")
            page = pdf.pages[item.page - 1]
            size, box, matrix = page_geometry(page)
            form = out.copy_foreign(page.as_form_xobject())
            form.BBox = pikepdf.Array(box)
            form.Matrix = pikepdf.Array([1, 0, 0, 1, 0, 0])
            forms.append((form, matrix))
            sizes.append(size)
            sources.append(
                {
                    "file": index,
                    "page": item.page,
                    "quantity": item.quantity,
                    "width": size[0],
                    "height": size[1],
                    "type": "pdf" if path.suffix == ".pdf" else "image",
                }
            )
        sheets = pack(sizes, items, params)
        for poses in sheets[:2] if preview else sheets:
            sheet = out.add_blank_page(
                page_size=(params.sheet_width * mm, params.sheet_height * mm)
            )
            commands, resources = [], {}
            for pose in poses:
                form, normalization = forms[pose.file]
                if pose.file not in resources:
                    resources[pose.file] = sheet.add_resource(form, pikepdf.Name.XObject)
                x, y = pose.x * mm, pose.y * mm
                placement = (
                    (1, 0, 0, 1, x, y)
                    if pose.rotation == 0
                    else (0, 1, -1, 0, x + pose.width * mm, y)
                )
                matrix = transform(placement, normalization)
                commands.append(
                    "q "
                    + " ".join(f"{n:.10f}" for n in matrix)
                    + f" cm {resources[pose.file]} Do Q"
                )
            sheet.contents_add("\n".join(commands).encode("ascii"))
        path = folder / "imposition.pdf"
        out.save(path)
    out.close()
    area = sum(w * h * item.quantity for (w, h), item in zip(sizes, items, strict=True))
    occupancy = area / (len(sheets) * params.sheet_width * params.sheet_height) * 100
    metrics = {
        "Fichiers": len(files),
        "Exemplaires": sum(item.quantity for item in items),
        "Planches": len(sheets),
        "Surface utilisée (%)": round(occupancy, 1),
    }
    manifest = folder / "plan-imposition.json"
    write_json(
        manifest,
        {
            "settings": params.model_dump(),
            "sources": sources,
            "origin": "bottom_left",
            "unit": "mm",
            "metrics": metrics,
            "sheets": [[asdict(pose) for pose in sheet] for sheet in sheets],
        },
    )
    return ToolResult(
        tool="granola",
        summary=f"{metrics['Exemplaires']} exemplaires répartis sur "
        f"{len(sheets)} planche(s), sans exemplaire supplémentaire.",
        metrics=metrics,
        warnings=[
            "Imprimer à 100 %. La zone visible des PDF est conservée, fonds perdus inclus. "
            "Les images sont incorporées en RVB ; contrôlez leur résolution et leurs couleurs. "
            "Aucun repère de coupe n’est ajouté."
        ],
        artifacts=[
            artifact(path, "Planches imposées"),
            artifact(manifest, "Plan de placement JSON"),
        ],
    )
