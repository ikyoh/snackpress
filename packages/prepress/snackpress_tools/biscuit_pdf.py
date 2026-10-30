"""Recover closed PDF paths, with an explicit raster silhouette alternative."""

import ctypes

import pypdfium2 as pdfium
from shapely import Polygon, box, unary_union

from .biscuit_svg import filled_rings, path_rings
from .common import open_pdf
from .granola_shapes import bitmap


def read_pdf(path, p):
    with open_pdf(path) as pdf:
        if p.page > len(pdf.pages):
            raise ValueError(
                f"Ce PDF contient {len(pdf.pages)} page(s). Choisissez une page existante."
            )
        page_info = pdf.pages[p.page - 1]
        if p.pdf_method == "vector" and (
            int(page_info.obj.get("/Rotate", 0)) % 360
            or float(page_info.obj.get("/UserUnit", 1)) != 1
        ):
            raise ValueError(
                "Normalisez la rotation et les unités du PDF ou utilisez la silhouette."
            )
    image = bitmap(path, p.page - 1)
    with pdfium.PdfDocument(str(path)) as pdf:
        page = pdf[p.page - 1]
        page_width, page_height = page.get_size()
        height = p.width * page_height / page_width
        page.close()
    if p.pdf_method == "silhouette":
        return None, image, height
    raw = pdfium.raw
    shapes = []
    index = 0
    with pdfium.PdfDocument(str(path)) as pdf:
        page = pdf[p.page - 1]
        left, bottom, right, top = page.get_bbox()
        factor = p.width / (right - left)

        def walk(form=None, parent=None, depth=0):
            nonlocal index
            if depth > 15:
                raise ValueError("PDF trop imbriqué. Aplatissez-le ou utilisez la silhouette.")
            parent = parent or pdfium.PdfMatrix()
            for obj in page.get_objects(max_depth=1, form=form):
                matrix = obj.get_matrix().multiply(parent)
                if obj.type == raw.FPDF_PAGEOBJ_FORM:
                    group_clip = raw.FPDFPageObj_GetClipPath(obj)
                    if group_clip and raw.FPDFClipPath_CountPaths(group_clip) > 0:
                        raise ValueError("Groupe PDF masqué : utilisez la silhouette.")
                    walk(obj, matrix, depth + 1)
                elif obj.type == raw.FPDF_PAGEOBJ_PATH:
                    index += 1
                    if index > 2000:
                        raise ValueError("PDF trop complexe : 2 000 tracés maximum.")
                    if p.pdf_object and index != p.pdf_object:
                        continue
                    clip = raw.FPDFPageObj_GetClipPath(obj)
                    count = raw.FPDFPath_CountSegments(obj)
                    if count > 10000:
                        raise ValueError("Tracé PDF trop complexe : simplifiez-le avant l’import.")
                    parts, controls = [], []
                    for i in range(count):
                        segment = raw.FPDFPath_GetPathSegment(obj, i)
                        x, y = ctypes.c_float(), ctypes.c_float()
                        if not raw.FPDFPathSegment_GetPoint(segment, x, y):
                            raise ValueError("Tracé PDF illisible.")
                        x, y = matrix.on_point(x.value, y.value)
                        x, y = (x - left) * factor, (top - y) * factor
                        kind = raw.FPDFPathSegment_GetType(segment)
                        if kind == raw.FPDF_SEGMENT_MOVETO:
                            parts.append(f"M{x} {y}")
                        elif kind == raw.FPDF_SEGMENT_LINETO:
                            parts.append(f"L{x} {y}")
                        elif kind == raw.FPDF_SEGMENT_BEZIERTO:
                            controls.extend([x, y])
                            if len(controls) == 6:
                                parts.append("C" + " ".join(map(str, controls)))
                                controls = []
                        if raw.FPDFPathSegment_GetClose(segment):
                            parts.append("Z")
                    fill, stroke = ctypes.c_int(), ctypes.c_int()
                    raw.FPDFPath_GetDrawMode(obj, fill, stroke)
                    if fill.value:
                        closed = []
                        for part in parts:
                            if part.startswith("M") and closed and closed[-1] != "Z":
                                closed.append("Z")
                            closed.append(part)
                        if closed and closed[-1] != "Z":
                            closed.append("Z")
                        parts = closed
                    try:
                        shape = filled_rings(path_rings(" ".join(parts)), fill.value == 1)
                    except ValueError as exc:
                        raise ValueError(
                            f"Tracé PDF n°{index} : {exc} Essayez un autre tracé ou la silhouette."
                        ) from exc
                    for clip_index in range(
                        max(0, raw.FPDFClipPath_CountPaths(clip)) if clip else 0
                    ):
                        points = []
                        for segment_index in range(
                            raw.FPDFClipPath_CountPathSegments(clip, clip_index)
                        ):
                            seg = raw.FPDFClipPath_GetPathSegment(clip, clip_index, segment_index)
                            if raw.FPDFPathSegment_GetType(seg) == raw.FPDF_SEGMENT_BEZIERTO:
                                raise ValueError("Masque PDF courbe : utilisez la silhouette.")
                            cx, cy = ctypes.c_float(), ctypes.c_float()
                            raw.FPDFPathSegment_GetPoint(seg, cx, cy)
                            px, py = parent.on_point(cx.value, cy.value)
                            points.append(((px - left) * factor, (top - py) * factor))
                        if len(points) < 4:
                            raise ValueError("Masque PDF complexe : utilisez la silhouette.")
                        mask = Polygon(points)
                        if not mask.is_valid or not mask.equals(box(*mask.bounds)):
                            raise ValueError("Masque PDF complexe : utilisez la silhouette.")
                        shape = shape.intersection(mask)
                    if not shape.is_empty and shape.area > 0:
                        shapes.append(shape)

        walk()
        page.close()
    if not shapes:
        raise ValueError(
            "Aucun tracé fermé correspondant. Changez le numéro ou utilisez la silhouette."
        )
    return unary_union(shapes), image, height
