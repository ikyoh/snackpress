"""Placement-only guides reused from the product proof renderer."""

import base64
from io import BytesIO

import pypdfium2 as pdfium

from .product_proof import component_guide


def placement_guides(folder, component):
    if not 40 <= component.width <= 500 or not 40 <= component.height <= 500:
        raise ValueError("Fortune Cookie accepte un produit de 40 à 500 mm par côté.")
    if component.bleed > 20:
        raise ValueError("Fortune Cookie accepte un fond perdu de 0 à 20 mm par côté.")
    path, (width, height), (left, bottom, _, _) = component_guide(folder, component)
    with pdfium.PdfDocument(str(path)) as pdf:
        page = pdf[0]
        scale = min(4, 1600 / max(page.get_size()))
        bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 0), rev_byteorder=True)
        try:
            output = BytesIO()
            bitmap.to_pil().save(output, format="PNG")
        finally:
            bitmap.close()
    return {
        "url": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(),
        "x": round(-left, 4),
        "y": round(-(height - bottom - component.height), 4),
        "width": round(width, 4),
        "height": round(height, 4),
    }
