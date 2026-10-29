"""Build reusable contour-nesting pairs, then pack their envelopes with other jobs."""

from collections import defaultdict

import numpy as np
from shapely import LineString, MultiPoint, box, constrained_delaunay_triangles, unary_union
from shapely.affinity import rotate, translate

from .catalog import GranolaItem
from .granola_shapes import polygons, rings

EPS = 1e-6


def oriented(geometry, angle):
    turned = rotate(geometry, angle, origin=(0, 0))
    left, bottom, _, _ = turned.bounds
    return translate(turned, xoff=-left, yoff=-bottom)


def convex_parts(geometry):
    hull = geometry.convex_hull
    if geometry.area >= hull.area * (1 - 1e-8):
        return [hull]
    # Small concave contours get an exact no-fit polygon. For complex outlines,
    # convex contacts are a bounded candidate set; final collision checks stay exact.
    if sum(len(p.exterior.coords) for p in polygons(geometry)) > 24:
        return [hull]
    return list(constrained_delaunay_triangles(geometry).geoms)


def no_fit(first, second, gap):
    sums = []
    for a in convex_parts(first):
        aa = np.asarray(a.exterior.coords)[:-1]
        for b in convex_parts(second):
            bb = np.asarray(b.exterior.coords)[:-1]
            differences = (aa[:, None, :] - bb[None, :, :]).reshape(-1, 2)
            sums.append(MultiPoint(differences).convex_hull)
    return unary_union(sums).buffer(gap, join_style="mitre")


def coordinates(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type in {"Point", "LineString"}:
        return list(geometry.coords)
    return [point for part in geometry.geoms for point in coordinates(part)]


def contacts(boundary, first_size, second_size):
    points = [point for ring in rings(boundary) for point in ring]
    for polygon in polygons(boundary):
        for ring in polygon.interiors:
            points.extend(list(ring.coords)[:-1])
    left, bottom, right, top = boundary.bounds
    for x in (0, first_size[0] - second_size[0]):
        line = LineString([(x, bottom - 1), (x, top + 1)])
        points.extend(coordinates(boundary.boundary.intersection(line)))
    for y in (0, first_size[1] - second_size[1]):
        line = LineString([(left - 1, y), (right + 1, y)])
        points.extend(coordinates(boundary.boundary.intersection(line)))
    return set((round(x, 8), round(y, 8)) for x, y in points)


def pair_template(first_geometry, second_geometry, params):
    available_width = params.sheet_width - 2 * params.margin
    available_height = params.sheet_height - 2 * params.margin
    angles = (0, 90, 180, 270) if params.rotation == "auto" else (0,)
    best = None
    for first_angle in angles[:2] if params.rotation == "auto" else angles:
        first = oriented(first_geometry, first_angle)
        aw, ah = first.bounds[2:]
        for second_angle in angles:
            second = oriented(second_geometry, second_angle)
            bw, bh = second.bounds[2:]
            boundary = no_fit(first, second, params.gap)
            candidates = []
            for x, y in contacts(boundary, (aw, ah), (bw, bh)):
                left, bottom = min(0, x), min(0, y)
                width, height = max(aw, x + bw) - left, max(ah, y + bh) - bottom
                if width > available_width + EPS or height > available_height + EPS:
                    continue
                score = (
                    (height, width)
                    if params.optimization == "width"
                    else ((width + 2 * params.margin) * (height + 2 * params.margin), height)
                )
                candidates.append((score, x, y, width, height, left, bottom))
            for score, x, y, width, height, left, bottom in sorted(candidates)[:512]:
                if best is not None and score >= best[0]:
                    break
                moved = translate(second, xoff=x, yoff=y)
                if first.intersection(moved).area > EPS or first.distance(moved) + EPS < params.gap:
                    continue
                best = (
                    score,
                    (width, height),
                    [
                        (-left, -bottom, aw, ah, first_angle),
                        (x - left, y - bottom, bw, bh, second_angle),
                    ],
                )
                break
    return None if best is None else best[1:]


def nest(sizes, items, geometries, params):
    from .granola import Pose, layout_score, pack

    def pair_score(sheets):
        score = layout_score(sheets, params.margin, params.optimization)
        if params.optimization == "width":
            # Compact pair envelopes leave room for more pairs across the sheet.
            # Width filling is evaluated on the complete job, not on a lone pair.
            return score[:2] + (-score[3],)
        return score

    groups = defaultdict(list)
    for file, (size, item, geometry) in enumerate(zip(sizes, items, geometries, strict=True)):
        key = (*size, geometry.normalize().wkb if geometry is not None else None)
        groups[key].extend((file, copy) for copy in range(1, item.quantity + 1))
    envelopes, quantities, members, patterns = [], [], [], []
    paired = 0
    remaining = []

    def add(size, allocations, offsets):
        envelopes.append(size)
        quantities.append(GranolaItem(quantity=len(allocations)))
        members.append(allocations)
        patterns.append(offsets)

    for (width, height, _), copies in groups.items():
        geometry = geometries[copies[0][0]]
        if geometry is not None and geometry.area < width * height * 0.999 and len(copies) > 1:
            template = pair_template(geometry, geometry, params)
            if template:
                size, offsets = template
                baseline = pack([(width, height)], [GranolaItem(quantity=2)], params)
                proposal = [[Pose(0, 1, params.margin, params.margin, *size, 0)]]
                if pair_score(proposal) < pair_score(baseline):
                    count = len(copies) // 2
                    add(size, [copies[n : n + 2] for n in range(0, count * 2, 2)], offsets)
                    paired += count
                    copies = copies[count * 2 :]
        if copies:
            remaining.append({"size": (width, height), "geometry": geometry, "copies": copies})
    # Different files and different outlines can also complement one another.
    # Bound pair-template work independently of production quantities.
    combinations = []
    for i, first in enumerate(remaining):
        for j in range(i + 1, len(remaining)):
            second = remaining[j]
            if first["geometry"] is None and second["geometry"] is None:
                continue
            spare = sum(
                w * h - (g["geometry"].area if g["geometry"] is not None else w * h)
                for g in (first, second)
                for w, h in [g["size"]]
            )
            combinations.append((-spare, i, j))
    proposals = []
    for _, i, j in sorted(combinations)[:64]:
        first, second = remaining[i], remaining[j]
        a = first["geometry"] if first["geometry"] is not None else box(0, 0, *first["size"])
        b = second["geometry"] if second["geometry"] is not None else box(0, 0, *second["size"])
        template = pair_template(a, b, params)
        if template is None:
            continue
        size, offsets = template
        baseline = pack([first["size"], second["size"]], [GranolaItem(), GranolaItem()], params)
        proposed = [[Pose(0, 1, params.margin, params.margin, *size, 0)]]
        before = pair_score(baseline)
        after = pair_score(proposed)
        if after < before:
            proposals.append(
                (-(before[0] - after[0]), -(before[1] - after[1]), i, j, size, offsets)
            )
    for _, _, i, j, size, offsets in sorted(proposals):
        first, second = remaining[i], remaining[j]
        count = min(len(first["copies"]), len(second["copies"]))
        if not count:
            continue
        add(
            size,
            [
                [a, b]
                for a, b in zip(first["copies"][:count], second["copies"][:count], strict=True)
            ],
            offsets,
        )
        first["copies"], second["copies"] = first["copies"][count:], second["copies"][count:]
        paired += count
    for group in remaining:
        if group["copies"]:
            width, height = group["size"]
            add(group["size"], [[copy] for copy in group["copies"]], [(0, 0, width, height, 0)])
    try:
        packed = pack(envelopes, quantities, params)
    except ValueError:
        return pack(sizes, items, params), 0
    sheets = []
    for sheet in packed:
        poses = []
        for envelope in sheet:
            allocation = members[envelope.file][envelope.copy - 1]
            envelope_height = envelopes[envelope.file][1]
            for (file, copy), (x, y, width, height, rotation) in zip(
                allocation, patterns[envelope.file], strict=True
            ):
                if envelope.rotation == 90:
                    x, y, width, height = envelope_height - y - height, x, height, width
                poses.append(
                    Pose(
                        file,
                        copy,
                        envelope.x + x,
                        envelope.y + y,
                        width,
                        height,
                        (rotation + envelope.rotation) % 360,
                    )
                )
        sheets.append(poses)
    # Useful pairs can still make a mixed job harder to pack. Compare complete
    # layouts, including the sheet count, rather than judging pairs alone.
    try:
        baseline = pack(sizes, items, params)
    except ValueError:
        # Nesting may bring a job back below the 200-sheet limit.
        baseline = None
    if baseline:
        before = layout_score(baseline, params.margin, params.optimization)
        after = layout_score(sheets, params.margin, params.optimization)
        baseline_better = (
            before[:3] < after[:3] if params.optimization == "width" else before <= after
        )
        if baseline_better:
            return baseline, 0
    return sheets, paired
