"""Biscuit: calibrated silhouettes and closed vector offset contours."""

from xml.sax.saxutils import quoteattr

import numpy as np
from PIL import Image, ImageOps
from reportlab.lib.colors import CMYKColorSep, HexColor
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from shapely import Point, Polygon, box, unary_union
from shapely.affinity import scale, translate

from .biscuit_pdf import read_pdf
from .biscuit_svg import read_svg
from .catalog import ToolResult
from .common import artifact, new_canvas
from .granola_shapes import polygons


def image_geometry(path, p, image=None):
    try:
        if image is None:
            with Image.open(path) as original:
                if original.width * original.height > 20_000_000:
                    raise ValueError("Image trop grande : 20 millions de pixels maximum.")
                image = ImageOps.exif_transpose(original).convert("RGBA")
                image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Image illisible ou trop grande. Utilisez un PNG ou JPEG.") from exc
    pixels = np.asarray(image)
    alpha = pixels[:, :, 3]
    has_alpha = np.any(alpha < 255)
    mask = (
        alpha > p.threshold if has_alpha else np.min(pixels[:, :, :3], axis=2) < 255 - p.threshold
    )
    if not mask.any():
        raise ValueError("Aucun sujet détecté. Réduisez le seuil ou utilisez un fond transparent.")
    height = p.width * image.height / image.width
    pixel = p.width / image.width
    runs = []
    for row, values in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.pad(values.astype(np.int8), 1)))
        for start, end in zip(edges[::2], edges[1::2], strict=True):
            runs.append(box(start * pixel, row * pixel, end * pixel, (row + 1) * pixel))
        if len(runs) > 40000:
            raise ValueError("Image trop détaillée : augmentez le seuil ou simplifiez l’image.")
    return unary_union(runs), image, height, pixel


def source_geometry(files, p):
    if p.source != "shape" and len(files) != 1:
        raise ValueError("Importez un PDF, une image ou un SVG pour créer le contour.")
    if p.source == "shape":
        if files:
            raise ValueError("Retirez le fichier ou choisissez un mode d’import.")
        height = p.width if p.shape == "circle" else p.height
        if p.shape in {"circle", "ellipse"}:
            geometry = scale(
                Point(p.width / 2, height / 2).buffer(1, quad_segs=96),
                p.width / 2,
                height / 2,
                origin=(p.width / 2, height / 2),
            )
        elif p.radius > 0:
            if p.radius > min(p.width, height) / 2:
                raise ValueError("Le rayon ne peut pas dépasser la moitié du plus petit côté.")
            # A buffered point/line also handles semicircular ends exactly.
            from shapely import LineString

            core = box(p.radius, p.radius, p.width - p.radius, height - p.radius)
            if core.area == 0:
                core = LineString([(p.radius, p.radius), (p.width - p.radius, height - p.radius)])
                if core.length == 0:
                    core = Point(p.radius, p.radius)
            geometry = core.buffer(p.radius, quad_segs=64)
        else:
            geometry = box(0, 0, p.width, height)
        return geometry, None, height, 0
    path = files[0]
    if p.source == "pdf":
        if path.suffix.lower() != ".pdf":
            raise ValueError("Le mode PDF attend un fichier .pdf.")
        geometry, image, height = read_pdf(path, p)
        if geometry is None:
            return image_geometry(path, p, image)
        return geometry, image, height, 0
    if p.source == "image":
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("Le mode Image attend un PNG ou JPEG.")
        return image_geometry(path, p)
    if path.suffix.lower() != ".svg":
        raise ValueError("Le mode SVG attend un fichier .svg.")
    geometry = read_svg(path)
    left, top, right, bottom = geometry.bounds
    if right - left <= 0 or bottom - top <= 0:
        raise ValueError("SVG sans surface de découpe.")
    factor = p.width / (right - left)
    geometry = scale(translate(geometry, -left, -top), factor, factor, origin=(0, 0))
    return geometry, None, (bottom - top) * factor, 0


def cut_geometry(files, p):
    source, image, height, precision = source_geometry(files, p)
    pieces = [poly for poly in polygons(source) if poly.area >= p.min_area]
    if not pieces:
        raise ValueError("Toutes les formes sont sous la surface minimale. Réduisez ce réglage.")
    if p.selection == "largest":
        pieces = [max(pieces, key=lambda poly: poly.area)]
    if p.holes == "fill":
        pieces = [Polygon(poly.exterior) for poly in pieces]
    source = unary_union(pieces)
    if p.source != "shape":
        source = source.simplify(p.smoothing, preserve_topology=True)
    result = source.buffer(p.offset, quad_segs=32, join_style=p.join) if p.offset else source
    if p.output_mode == "inverse":
        frame = box(
            -p.inverse_margin,
            -p.inverse_margin,
            p.width + p.inverse_margin,
            height + p.inverse_margin,
        )
        result = frame.difference(result)
    if result.is_empty:
        if p.output_mode == "inverse":
            raise ValueError(
                "La forme inversée est vide. Augmentez sa marge ou réduisez le décalage."
            )
        raise ValueError("Ce décalage fait disparaître toute la forme. Rapprochez-le de zéro.")
    if len(polygons(result)) > 300:
        raise ValueError(
            "Plus de 300 formes : augmentez la surface minimale ou gardez la plus grande."
        )
    return source, result, image, height, precision


def contours(geometry):
    for polygon in polygons(geometry):
        yield polygon.exterior
        yield from polygon.interiors


def generate(folder, files, p):
    source, result, image, height, precision = cut_geometry(files, p)
    bounds = unary_union([source, result, box(0, 0, p.width, height)]).bounds
    left, top, right, bottom = bounds
    margin = 3
    width, page_height = right - left + 2 * margin, bottom - top + 2 * margin
    dx, dy = margin - left, margin - top

    filled = p.output_mode != "path"
    colour = CMYKColorSep(
        *(v / 100 for v in (p.cyan, p.magenta, p.yellow, p.black)), spotName=p.spot_name
    )

    def draw(c, geometry, fill=False):
        path = c.beginPath()
        for ring in contours(geometry):
            points = list(ring.coords)
            x, y = points[0]
            path.moveTo((x + dx) * mm, (page_height - y - dy) * mm)
            for x, y in points[1:]:
                path.lineTo((x + dx) * mm, (page_height - y - dy) * mm)
            path.close()
        c.drawPath(path, stroke=int(not fill), fill=int(fill), fillMode=0)

    preview = folder / "apercu.pdf"
    c = new_canvas(preview, width, page_height)
    if image is not None:
        c.drawImage(
            ImageReader(image),
            dx * mm,
            (page_height - dy - height) * mm,
            width=p.width * mm,
            height=height * mm,
            mask="auto",
        )
    c.setStrokeColor(HexColor("#71667b"))
    c.setLineWidth(0.18 * mm)
    c.setDash(1 * mm, 0.7 * mm)
    draw(c, source)
    c.setDash()
    c.setStrokeColor(colour)
    c.setFillColor(colour)
    if filled:
        c.setFillAlpha(0.45)
    c.setLineWidth(0.25 * mm)
    draw(c, result, filled)
    c.showPage()
    c.save()

    pdf = folder / "decoupe.pdf"
    c = new_canvas(pdf, width, page_height)
    c.setStrokeColor(colour)
    c.setFillColor(colour)
    c.setFillOverprint(True)
    c.setStrokeOverprint(True)
    c.setLineWidth(0.1 * mm)
    draw(c, result, filled)
    c.showPage()
    c.save()

    svg = folder / "decoupe.svg"
    paths = []
    for ring in contours(result):
        points = list(ring.coords)[:-1]
        paths.append("M " + " L ".join(f"{x + dx:.6f},{y + dy:.6f}" for x, y in points) + " Z")
    rgb = [round(255 * (1 - v / 100) * (1 - p.black / 100)) for v in (p.cyan, p.magenta, p.yellow)]
    hex_colour = "#" + "".join(f"{v:02x}" for v in rgb)
    svg_fill, svg_stroke = (hex_colour, "none") if filled else ("none", hex_colour)
    svg.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.6f}mm" '
        f'height="{page_height:.6f}mm" viewBox="0 0 {width:.6f} {page_height:.6f}">'
        f"<title>Snackpress Biscuit</title><metadata>CMJN : {p.cyan:g}, {p.magenta:g}, "
        f"{p.yellow:g}, {p.black:g}</metadata>"
        f'<path id="CutContour" data-spot-name={quoteattr(p.spot_name)} '
        f'd="{" ".join(paths)}" fill="{svg_fill}" stroke="{svg_stroke}" '
        'stroke-width="0.1" fill-rule="evenodd"/></svg>',
        encoding="utf-8",
    )
    warnings = [
        "Le SVG et le PDF de découpe contiennent uniquement le tracé final. "
        "L’aperçu avec le visuel et les pointillés est réservé au contrôle."
    ]
    if precision:
        warnings.append(
            f"Détection du fond blanc ou de la transparence, sans détourage IA. "
            f"Précision de l’image analysée : environ {precision:.3f} mm/pixel."
        )
    if p.source == "svg":
        warnings.append(
            "Courbes SVG approchées en segments ; largeur recalibrée sur la forme. "
            "Les groupes et transformations sont appliqués."
        )
    warnings.append(
        "La teinte nommée et ses CMJN sont conservés dans le PDF. Le SVG utilise "
        "un aperçu RVB avec le nom et les CMJN en métadonnées."
    )
    if p.source == "pdf":
        warnings.append(
            "Page PDF recalibrée à la largeur source choisie. En mode vectoriel, "
            "seuls les chemins fermés sont récupérés, sans convertir textes et images."
        )
    before = sum(1 + len(poly.interiors) for poly in polygons(source))
    after = sum(1 + len(poly.interiors) for poly in polygons(result))
    if before != after:
        warnings.append(
            "Le décalage a changé le nombre de contours : vérifiez les trous et zones étroites."
        )
    x0, y0, x1, y1 = result.bounds
    return ToolResult(
        tool="biscuit",
        summary="Votre forme de découpe est prête.",
        metrics={
            "Largeur de découpe (mm)": round(x1 - x0, 3),
            "Hauteur de découpe (mm)": round(y1 - y0, 3),
            "Décalage (mm)": p.offset,
            "Teinte nommée": p.spot_name,
            "Contours fermés": after,
            "Points du tracé": sum(len(r.coords) - 1 for r in contours(result)),
        },
        warnings=warnings,
        artifacts=[
            artifact(preview, "Aperçu de contrôle"),
            artifact(svg, "Tracé de découpe SVG"),
            artifact(pdf, f"PDF vectoriel · {p.spot_name}"),
        ],
    )
