"""Impose numbered tickets in batches whose cut piles form consecutive books."""

from math import ceil

import pikepdf
from snackpress_imposition.geometry import Settings, calculate
from snackpress_imposition.pdf import PT

from .common import artifact, report, write_json


def cut_stack(count, per_book, poses):
    sheets, batches = [], []
    for first_book in range(0, ceil(count / per_book), poses):
        first = first_book * per_book
        depth = min(per_book, count - first)
        start_sheet = len(sheets)
        for level in range(depth):
            sheets.append(
                [
                    index if index < count else None
                    for pose in range(poses)
                    for index in [first + pose * per_book + level]
                ]
            )
        batches.append(
            {
                "first_sheet": start_sheet + 1,
                "last_sheet": len(sheets),
                "books": [
                    {
                        "pose": pose + 1,
                        "first_index": first + pose * per_book,
                        "last_index": min(first + (pose + 1) * per_book, count) - 1,
                    }
                    for pose in range(poses)
                    if first + pose * per_book < count
                ],
            }
        )
    return sheets, batches


def impose(folder, source, params, *, preview=False):
    layer = params.layer_template
    plan = calculate(
        Settings(
            sheet_width=layer.sheet_width,
            sheet_height=layer.sheet_height,
            margin=layer.margin,
            gap=layer.gap,
            trim_width=params.width,
            trim_height=params.height,
            bleed=params.pizza_template.bleed if params.pizza_template else 0,
            quantity=params.count,
            confirm_trim=True,
        )
    )
    # Pose 1 is at the top left, matching the gathering instructions.
    placements = sorted(plan.front, key=lambda pose: (-pose.y, pose.x))
    sheets, batches = cut_stack(params.count, params.tickets_per_book, plan.poses)
    path = folder / "imposition.pdf"
    with pikepdf.open(source) as pdf:
        out = pikepdf.Pdf.new()
        forms = {}
        for indices in sheets[:2] if preview else sheets:
            target = out.add_blank_page(page_size=(layer.sheet_width * PT, layer.sheet_height * PT))
            commands = []
            for index, pose in zip(indices, placements, strict=True):
                if index is None:
                    continue
                if index not in forms:
                    page = pdf.pages[index]
                    box = list(map(float, page.trimbox))
                    form = out.copy_foreign(page.as_form_xobject())
                    form.BBox = pikepdf.Array(page.mediabox)
                    form.Matrix = pikepdf.Array([1, 0, 0, 1, 0, 0])
                    forms[index] = (form, box)
                form, box = forms[index]
                name = target.add_resource(form, pikepdf.Name.XObject)
                x, y = pose.x * PT, pose.y * PT
                matrix = (
                    (1, 0, 0, 1, x - box[0], y - box[1])
                    if pose.rotation == 0
                    else (0, 1, -1, 0, x + box[3], y - box[0])
                )
                commands.append("q " + " ".join(f"{n:.8f}" for n in matrix) + f" cm {name} Do Q")
            commands.append("q 0 0 0 1 K 0.25 w")
            for mark in plan.marks:
                commands.append(
                    f"{mark.x1 * PT:.8f} {mark.y1 * PT:.8f} m "
                    f"{mark.x2 * PT:.8f} {mark.y2 * PT:.8f} l S"
                )
            commands.append("Q")
            target.contents_add("\n".join(commands).encode("ascii"))
        out.save(path)
    metrics = {
        "Billets": params.count,
        "Billets par souche": params.tickets_per_book,
        "Souches": ceil(params.count / params.tickets_per_book),
        "Poses": plan.poses,
        "Feuilles à tirer": len(sheets),
        "Lots de coupe": len(batches),
    }
    artifacts = [artifact(path, "Billets imposés pour coupe en souches")]
    if not preview:

        def serial(index):
            return params.prefix + str(params.start + index).zfill(params.digits)

        manifest = folder / "plan-souches.json"
        write_json(
            manifest,
            {
                "metrics": metrics,
                "grid": {"columns": plan.columns, "rows": plan.rows, "rotation": plan.rotation},
                "pose_order": "left_to_right_top_to_bottom",
                "placements": [pose.model_dump() for pose in placements],
                "batches": batches,
                "sheets": [[serial(i) if i is not None else None for i in row] for row in sheets],
            },
        )
        instructions = folder / "fiche-souches.pdf"
        report(
            instructions,
            "Fortune Cookie — coupe en souches",
            [
                *metrics.items(),
                ("Grille", f"{plan.columns} colonnes × {plan.rows} lignes ; {plan.rotation}°"),
                *[
                    (
                        f"Lot {i + 1} · feuilles {batch['first_sheet']} à {batch['last_sheet']}",
                        "; ".join(
                            f"Pose {book['pose']} : {serial(book['first_index'])} "
                            f"à {serial(book['last_index'])}"
                            for book in batch["books"]
                        ),
                    )
                    for i, batch in enumerate(batches)
                ],
            ],
            "Imprimer à 100 %, dans l’ordre du PDF, première feuille au-dessus de la pile. "
            "Séparer les lots indiqués avant la coupe. Couper chaque lot suivant les repères, "
            "puis ramasser les poses de gauche à droite et de haut en bas. Les emplacements "
            "vides restent blancs ; la dernière souche peut être incomplète. "
            "Les repères du gabarit Pizza sont absents de l’export.",
        )
        artifacts += [
            artifact(instructions, "Plan de coupe en souches"),
            artifact(manifest, "Ordre des billets et des souches JSON"),
            artifact(source, "Billets individuels sans imposition"),
        ]
    return artifacts, metrics, plan.warnings
