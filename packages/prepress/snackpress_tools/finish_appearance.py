"""Screen simulation of finishes, using black-on-white production masks."""

import math

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps

from .common import render_page


def dashed_contours(coverage, dpi):
    """Follow each mask contour, including holes, with 2 mm dashes and 1 mm gaps."""
    filled = np.asarray(coverage) >= 128
    padded = np.pad(filled, 1)
    height, width = filled.shape
    # Directed pixel edges keep the filled region on the right of the path.
    edges = np.zeros((4, height + 1, width + 1), dtype=bool)
    edges[0, :height, :width] = filled & ~padded[:-2, 1:-1]
    edges[1, :height, 1:] = filled & ~padded[1:-1, 2:]
    edges[2, 1:, 1:] = filled & ~padded[2:, 1:-1]
    edges[3, 1:, :width] = filled & ~padded[1:-1, :-2]
    dashed = np.zeros((height, width), dtype=np.uint8)
    steps = ((1, 0), (0, 1), (-1, 0), (0, -1))
    inside = ((0, 0), (-1, 0), (-1, -1), (0, -1))
    dash, gap = max(1, round(2 * dpi / 25.4)), max(1, round(dpi / 25.4))
    for direction, row, col in zip(*np.nonzero(edges), strict=True):
        if not edges[direction, row, col]:
            continue
        distance = 0
        while True:
            edges[direction, row, col] = False
            if distance % (dash + gap) < dash:
                ix, iy = inside[direction]
                dashed[row + iy, col + ix] = 255
            dx, dy = steps[direction]
            col, row = col + dx, row + dy
            distance += 1
            # Turn right first to keep diagonally touching regions separate.
            for turn in (1, 0, -1, 2):
                next_direction = (direction + turn) % 4
                if edges[next_direction, row, col]:
                    direction = next_direction
                    break
            else:
                break
    return Image.fromarray(dashed)


def simulate_finishes(
    image, finishes, masks, page_index, dpi, *, region=None, mask_page_counts=None
):
    """Preserve RGBA for transparent proof overlays; RGB callers stay flattened."""
    full_image = image
    if region is not None:
        image = image.crop(region)
    result = image.convert("RGBA")
    width, height = image.size
    for finish in finishes:
        style = finish.appearance
        if style.mode == "none":
            continue
        if finish.mask:
            count = (mask_page_counts or {}).get(finish.id)
            mask_page = page_index % count if count else page_index
            mask_image, _ = render_page(masks[finish.id], mask_page, dpi=dpi)
            coverage = ImageOps.invert(mask_image.convert("L")).resize(full_image.size)
            if region is not None:
                coverage = coverage.crop(region)
        else:
            coverage = Image.new("L", image.size, 255)
        if style.mode == "path":
            dashes = dashed_contours(coverage, dpi)
            # Pad with white so contours on the page boundary also remain visible.
            padded = ImageOps.expand(coverage, border=1, fill=0)
            coverage = ImageChops.subtract(padded, padded.filter(ImageFilter.MinFilter(3))).crop(
                (1, 1, width + 1, height + 1)
            )
        start = np.array([int(style.color[i : i + 2], 16) for i in (1, 3, 5)])
        if style.mode == "area" and style.gradient:
            end = np.array([int(style.end_color[i : i + 2], 16) for i in (1, 3, 5)])
            angle = math.radians(style.angle)
            dx, dy = math.cos(angle), -math.sin(angle)
            position = np.arange(width)[None, :] * dx + np.arange(height)[:, None] * dy
            extent = position.max() - position.min()
            fraction = (position - position.min()) / max(extent, 1)
            if style.gradient_stops is None:
                pixels = start + fraction[..., None] * (end - start)
            else:
                stops = style.gradient_stops
                positions = [0, *(stop.position / 100 for stop in stops), 1]
                channels = np.array(
                    [
                        start,
                        *([int(stop.color[i : i + 2], 16) for i in (1, 3, 5)] for stop in stops),
                        end,
                    ]
                )
                pixels = np.stack(
                    [np.interp(fraction, positions, channels[:, channel]) for channel in range(3)],
                    axis=-1,
                )
            layer = Image.fromarray(np.uint8(np.clip(np.round(pixels), 0, 255))).convert("RGBA")
        else:
            layer = Image.new("RGBA", image.size, style.color)
        opacity = style.alpha if style.mode == "area" else 1
        layer.putalpha(coverage.point(lambda value: round(value * opacity)))
        result = Image.alpha_composite(result, layer)
        if style.mode == "path":
            dashed_layer = Image.new("RGBA", image.size, style.dash_color)
            dashed_layer.putalpha(ImageChops.multiply(coverage, dashes))
            result = Image.alpha_composite(result, dashed_layer)
    if full_image.mode != "RGBA":
        result = result.convert("RGB")
    if region is not None:
        displayed = full_image.copy()
        displayed.paste(result, region)
        return displayed
    return result
