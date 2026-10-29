"""Estimate exterior printing silhouettes; keep native PDF content for composition."""

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps
from shapely import Polygon, box, unary_union
from shapely.affinity import translate


def polygons(geometry):
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [p for p in geometry.geoms if p.geom_type == "Polygon"]


def rings(geometry):
    return [list(p.exterior.coords)[:-1] for p in polygons(geometry)]


def bitmap(path, page_index):
    if path.suffix == ".pdf":
        with pdfium.PdfDocument(str(path)) as pdf:
            page = pdf[page_index]
            width, height = page.get_size()
            rendered = page.render(
                scale=min(4, 1600 / max(width, height)),
                fill_color=(255, 255, 255, 0),
                rev_byteorder=True,
                draw_annots=False,
            )
            try:
                return rendered.to_pil().convert("RGBA").copy()
            finally:
                rendered.close()
                page.close()
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("RGBA")
        image.thumbnail((1600, 1600), Image.Resampling.BOX)
        return image.copy()


def exterior_mask(mask, width, height):
    rows, cols = mask.shape
    padded = np.pad(mask, 1)
    edges = np.zeros((4, rows + 1, cols + 1), dtype=bool)
    edges[0, :rows, :cols] = mask & ~padded[:-2, 1:-1]
    edges[1, :rows, 1:] = mask & ~padded[1:-1, 2:]
    edges[2, 1:, 1:] = mask & ~padded[2:, 1:-1]
    edges[3, 1:, :cols] = mask & ~padded[1:-1, :-2]
    if np.count_nonzero(edges) > 50000:
        ys, xs = np.nonzero(mask)
        return box(
            xs.min() * width / cols,
            (rows - ys.max() - 1) * height / rows,
            (xs.max() + 1) * width / cols,
            (rows - ys.min()) * height / rows,
        )
    steps = ((1, 0), (0, 1), (-1, 0), (0, -1))
    paths = []
    for direction, row, col in zip(*np.nonzero(edges), strict=True):
        if not edges[direction, row, col]:
            continue
        points = []
        while True:
            points.append((col * width / cols, (rows - row) * height / rows))
            edges[direction, row, col] = False
            dx, dy = steps[direction]
            col, row = col + dx, row + dy
            for turn in (1, 0, -1, 2):
                next_direction = (direction + turn) % 4
                if edges[next_direction, row, col]:
                    direction = next_direction
                    break
            else:
                break
        if len(points) > 2:
            polygon = Polygon(points)
            if polygon.is_valid and polygon.area > 0:
                paths.append(polygon)
    return unary_union(paths)


def detect(path, page_index, size, tolerance):
    image = bitmap(path, page_index)
    pixels = np.asarray(image)
    alpha = pixels[:, :, 3]
    mask = (
        alpha > 16
        if np.count_nonzero(alpha <= 16) > alpha.size * 0.01
        else np.min(pixels[:, :, :3], axis=2) < 255 - tolerance
    )
    width, height = size
    precision = max(width / image.width, height / image.height)
    if not mask.any() or mask.all():
        return None, (0, 0), size, precision, "rectangle"
    raw = exterior_mask(mask, width, height)
    if raw.is_empty:
        return None, (0, 0), size, precision, "rectangle"
    # White holes remain inside the printing piece instead of receiving other poses.
    raw = unary_union([Polygon(p.exterior) for p in polygons(raw)])
    hull = raw.convex_hull
    if hull.area <= raw.area * 1.02 or len(polygons(raw)) > 16:
        geometry = hull
    else:
        geometry = (
            raw.simplify(precision, preserve_topology=True)
            .buffer(precision * 1.01, join_style="mitre")
            .intersection(box(0, 0, width, height))
        )
        if not geometry.covers(raw):
            geometry = geometry.union(raw)
    left, bottom, right, top = geometry.bounds
    local = translate(geometry, xoff=-left, yoff=-bottom)
    frame = box(0, 0, right - left, top - bottom)
    if frame.area - local.area < frame.area * 0.001:
        local, kind = frame, "rectangle"
    else:
        # This is only a display label; retain the conservative geometry for packing.
        simplified = local.convex_hull.simplify(precision * 4, preserve_topology=False)
        kind = (
            "triangle"
            if simplified.geom_type == "Polygon"
            and len(simplified.exterior.coords) == 4
            and simplified.area >= local.area * 0.95
            else "contour"
        )
    if (
        kind == "rectangle"
        and max(abs(left), abs(bottom), abs(right - width), abs(top - height)) < 1e-7
    ):
        return None, (0, 0), size, precision, kind
    return local, (left, bottom), (right - left, top - bottom), precision, kind
