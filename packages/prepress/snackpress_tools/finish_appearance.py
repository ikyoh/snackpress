"""Screen simulation of finishes, using black-on-white production masks."""

import math

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps

from .common import render_page


def simulate_finishes(image, finishes, masks, page_index, dpi):
    result = image.convert("RGBA")
    width, height = image.size
    for finish in finishes:
        style = finish.appearance
        if style.mode == "none":
            continue
        if finish.mask:
            mask_image, _ = render_page(masks[finish.id], page_index, dpi=dpi)
            coverage = ImageOps.invert(mask_image.convert("L")).resize(image.size)
        else:
            coverage = Image.new("L", image.size, 255)
        if style.mode == "path":
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
            pixels = start + fraction[..., None] * (end - start)
            layer = Image.fromarray(np.uint8(np.clip(np.round(pixels), 0, 255))).convert("RGBA")
        else:
            layer = Image.new("RGBA", image.size, style.color)
        opacity = style.alpha if style.mode == "area" else 1
        layer.putalpha(coverage.point(lambda value: round(value * opacity)))
        result = Image.alpha_composite(result, layer)
    return result.convert("RGB")
