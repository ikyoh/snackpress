"""Read geometric SVG only. Never execute scripts or resolve external resources."""

import math
import re
from xml.etree import ElementTree as ET

import numpy as np
from reportlab.graphics.svgpath import SvgPath
from shapely import Polygon, box, polygonize, unary_union
from shapely.affinity import affine_transform, scale

NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"


def numbers(value):
    if re.sub(NUMBER, "", value).strip(" ,\t\r\n"):
        raise ValueError("Coordonnées SVG invalides : utilisez des unités internes sans suffixe.")
    result = [float(n) for n in re.findall(NUMBER, value)]
    if any(not math.isfinite(n) or abs(n) > 1e8 for n in result):
        raise ValueError("Coordonnées SVG hors limites.")
    return result


def filled_rings(rings, evenodd=False):
    valid = [Polygon(ring) for ring in rings if len(ring) >= 4]
    if any(not p.is_valid for p in valid):
        raise ValueError("Le tracé se croise. Corrigez ses intersections avant l’import.")
    if not valid:
        raise ValueError("Aucun contour fermé détecté.")
    signs = [1 if p.exterior.is_ccw else -1 for p in valid]
    faces = polygonize([unary_union([p.boundary for p in valid])])
    kept = []
    for face in faces.geoms:
        point = face.representative_point()
        winding = sum(s for p, s in zip(valid, signs, strict=True) if p.covers(point))
        if (winding % 2 != 0) if evenodd else winding != 0:
            kept.append(face)
    return unary_union(kept)


def path_rings(value):
    try:
        path = SvgPath(value)
    except Exception as exc:
        raise ValueError("Chemin SVG illisible. Réexportez un SVG avec des tracés fermés.") from exc
    if len(path.operators) > 10000:
        raise ValueError("SVG trop complexe : simplifiez les tracés avant l’import.")
    rings, points, index = [], [], 0
    for op in path.operators:
        if op in (0, 1):  # moveTo / lineTo
            point = tuple(path.points[index : index + 2])
            index += 2
            if op == 0 and points:
                if points[0] != points[-1]:
                    raise ValueError("Un chemin SVG est ouvert. Fermez-le avant l’import.")
                rings.append(points)
                points = []
            points.append(point)
        elif op == 2:  # cubic Bezier, including converted arcs and quadratics
            if not points:
                raise ValueError("Chemin SVG sans point de départ.")
            a = np.array(points[-1])
            b, c, d = np.array(path.points[index : index + 6]).reshape(3, 2)
            index += 6
            for t in np.linspace(0, 1, 33)[1:]:
                points.append(
                    tuple(
                        (1 - t) ** 3 * a
                        + 3 * (1 - t) ** 2 * t * b
                        + 3 * (1 - t) * t * t * c
                        + t**3 * d
                    )
                )
        elif op == 3:
            if points:
                points.append(points[0])
                rings.append(points)
                points = []
    if points:
        if points[0] != points[-1]:
            raise ValueError("Un chemin SVG est ouvert. Fermez-le avant l’import.")
        rings.append(points)
    return rings


def transform(value):
    matrix = np.eye(3)
    parts = list(re.finditer(r"([a-zA-Z]+)\s*\(([^)]*)\)", value))
    if re.sub(r"[a-zA-Z]+\s*\([^)]*\)", "", value).strip(" ,\t\n"):
        raise ValueError("Transformation SVG invalide.")
    for part in parts:
        name, args = part.group(1), numbers(part.group(2))
        m = np.eye(3)
        if name == "matrix" and len(args) == 6:
            a, b, c, d, e, f = args
            m = np.array([[a, c, e], [b, d, f], [0, 0, 1]])
        elif name == "translate" and len(args) in (1, 2):
            m[0, 2], m[1, 2] = args[0], args[1] if len(args) == 2 else 0
        elif name == "scale" and len(args) in (1, 2):
            m[0, 0], m[1, 1] = args[0], args[-1]
        elif name == "rotate" and len(args) in (1, 3):
            angle = math.radians(args[0])
            m[:2, :2] = [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
            if len(args) == 3:
                center = np.array(args[1:])
                m[:2, 2] = center - m[:2, :2] @ center
        elif name in ("skewX", "skewY") and len(args) == 1:
            m[0 if name == "skewX" else 1, 1 if name == "skewX" else 0] = math.tan(
                math.radians(args[0])
            )
        else:
            raise ValueError("Transformation SVG non prise en charge.")
        matrix = matrix @ m
    return matrix


def read_svg(path):
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024 or b"<!" in raw:
        raise ValueError("SVG trop volumineux ou contenant des déclarations XML non autorisées.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("SVG illisible. Réexportez le fichier.") from exc
    if root.tag.split("}")[-1] != "svg":
        raise ValueError("Le fichier ne contient pas de document SVG.")
    if sum(1 for _ in root.iter()) > 2000:
        raise ValueError("SVG trop complexe : 2 000 éléments maximum.")
    geometries = []

    def visit(element, parent, inherited):
        tag = element.tag.split("}")[-1]
        if tag in {"defs", "title", "desc", "metadata", "namedview"}:
            return
        if tag not in {"svg", "g", "path", "rect", "circle", "ellipse", "polygon"}:
            raise ValueError(
                "SVG : convertissez textes, images, clones et effets en tracés fermés."
            )
        style = {**inherited, **element.attrib}
        for item in element.get("style", "").split(";"):
            if ":" in item:
                k, v = item.split(":", 1)
                style[k.strip()] = v.strip()
        if style.get("display") == "none" or style.get("visibility") == "hidden":
            return
        if any(k in style and style[k] != "none" for k in ("clip-path", "mask", "filter")):
            raise ValueError("SVG : appliquez les masques et effets avant l’import.")
        matrix = parent @ transform(element.get("transform", ""))
        if tag in {"svg", "g"}:
            if tag == "svg" and element is not root:
                raise ValueError("SVG imbriqués : aplatissez le document avant l’import.")
            for child in element:
                visit(
                    child,
                    matrix,
                    {
                        k: v
                        for k, v in style.items()
                        if k
                        in {"fill-rule", "display", "visibility", "clip-path", "mask", "filter"}
                    },
                )
            return

        def n(key, default="0"):
            values = numbers(element.get(key, default))
            if len(values) != 1:
                raise ValueError("Dimension SVG invalide.")
            return values[0]

        if tag == "path":
            rings = path_rings(element.get("d", ""))
            geometry = filled_rings(rings, style.get("fill-rule") == "evenodd")
        elif tag == "polygon":
            values = numbers(element.get("points", ""))
            if len(values) < 6 or len(values) % 2:
                raise ValueError("Polygone SVG invalide.")
            geometry = Polygon(list(zip(values[::2], values[1::2], strict=True)))
        elif tag == "rect":
            x, y, w, h = n("x"), n("y"), n("width"), n("height")
            if min(w, h) <= 0:
                raise ValueError("Rectangle SVG sans surface.")
            rx = min(max(n("rx", element.get("ry", "0")), 0), w / 2)
            ry = min(max(n("ry", element.get("rx", "0")), 0), h / 2)
            if rx > 0 and ry > 0:
                unit = box((x + rx) / rx, (y + ry) / ry, (x + w - rx) / rx, (y + h - ry) / ry)
                # Zero-width inner rectangles are handled by their boundary buffer.
                geometry = scale(unit.buffer(1, quad_segs=32), rx, ry, origin=(0, 0))
            else:
                geometry = box(x, y, x + w, y + h)
        else:
            cx, cy = n("cx"), n("cy")
            rx, ry = (n("r"), n("r")) if tag == "circle" else (n("rx"), n("ry"))
            if min(rx, ry) <= 0:
                raise ValueError("Ellipse SVG sans surface.")
            from shapely import Point

            geometry = scale(Point(cx, cy).buffer(1, quad_segs=64), rx, ry, origin=(cx, cy))
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError("Forme SVG invalide ou sans surface.")
        geometries.append(
            affine_transform(
                geometry,
                [
                    matrix[0, 0],
                    matrix[0, 1],
                    matrix[1, 0],
                    matrix[1, 1],
                    matrix[0, 2],
                    matrix[1, 2],
                ],
            )
        )

    visit(root, np.eye(3), {})
    if not geometries:
        raise ValueError("Aucune forme de découpe trouvée dans le SVG.")
    geometry = unary_union(geometries)
    if geometry.is_empty or not all(math.isfinite(n) for n in geometry.bounds):
        raise ValueError("SVG sans surface ou hors limites.")
    return geometry
