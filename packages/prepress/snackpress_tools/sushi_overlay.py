"""Append native spot-colour rectangles in the source page coordinate system."""

from math import isfinite

import pikepdf
from reportlab.lib.units import mm

from .catalog import ToolResult
from .common import artifact, open_pdf


def add_contours(folder, source, settings):
    target = folder / "contours.pdf"
    fallback_pages = []
    with open_pdf(source) as pdf:
        tint = pdf.make_indirect(
            pikepdf.Dictionary(
                FunctionType=2,
                Domain=[0, 1],
                C0=[0, 0, 0, 0],
                C1=[0, 1, 0, 0],
                N=1,
            )
        )
        spot = pdf.make_indirect(
            pikepdf.Array(
                [
                    pikepdf.Name.Separation,
                    pikepdf.Name("/" + settings.cut_name),
                    pikepdf.Name.DeviceCMYK,
                    tint,
                ]
            )
        )
        overprint = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.ExtGState,
                OP=True,
                OPM=1,
            )
        )
        for index, page in enumerate(pdf.pages, 1):
            unit = float(page.obj.get("/UserUnit", 1))
            if not isfinite(unit) or unit <= 0:
                raise ValueError(f"Page {index} : unité PDF invalide.")
            media = [float(v) for v in page.mediabox]
            crop = [float(v) for v in page.cropbox]
            visible = [
                max(media[0], crop[0]),
                max(media[1], crop[1]),
                min(media[2], crop[2]),
                min(media[3], crop[3]),
            ]
            if settings.pdf_box == "trim" and "/TrimBox" in page.obj:
                box = [float(v) for v in page.trimbox]
            else:
                box = [float(v) for v in visible]
                if settings.pdf_box == "trim":
                    fallback_pages.append(index)
            if (
                not all(isfinite(v) for v in box)
                or box[0] < visible[0] - 1e-5
                or box[1] < visible[1] - 1e-5
                or box[2] > visible[2] + 1e-5
                or box[3] > visible[3] + 1e-5
            ):
                raise ValueError(f"Page {index} : format fini hors de la zone visible du PDF.")
            inset = settings.pdf_inset * mm / unit
            x, y = box[0] + inset, box[1] + inset
            width, height = box[2] - box[0] - 2 * inset, box[3] - box[1] - 2 * inset
            if width <= 0 or height <= 0:
                raise ValueError(f"Page {index} : le retrait ne laisse aucun rectangle de découpe.")
            # Shared/inherited resources must stay intact, including same-named resources.
            page.Resources = pikepdf.Dictionary(page.Resources)
            for kind in ("ColorSpace", "ExtGState"):
                page.Resources["/" + kind] = pikepdf.Dictionary(page.Resources.get("/" + kind, {}))
            colour_name = page.add_resource(spot, pikepdf.Name.ColorSpace)
            state_name = page.add_resource(overprint, pikepdf.Name.ExtGState)
            stroke = settings.cut_width * mm / unit
            # Isolate the original CTM, clipping and colour state before drawing the rectangle.
            page.contents_add(b"q\n", prepend=True)
            page.contents_add(
                (
                    f"\nQ\nq\n{state_name} gs\n{colour_name} CS\n1 SCN\n"
                    f"{stroke:.9f} w\n[] 0 d\n0 J\n0 j\n"
                    f"{x:.9f} {y:.9f} {width:.9f} {height:.9f} re\nS\nQ\n"
                ).encode("ascii")
            )
        pages = len(pdf.pages)
        pdf.save(target)
    warnings = []
    if fallback_pages:
        warnings.append(
            "TrimBox absente : contour placé sur le bord visible des pages "
            + ", ".join(map(str, fallback_pages))
            + "."
        )
    return ToolResult(
        tool="sushi",
        summary=(
            f"{pages} contour(s) rectangulaire(s) ajouté(s) au PDF "
            f"en ton direct « {settings.cut_name} »."
        ),
        metrics={"Pages": pages, "Rectangles de découpe": pages},
        warnings=warnings,
        artifacts=[artifact(target, "PDF avec contours de découpe")],
    )
