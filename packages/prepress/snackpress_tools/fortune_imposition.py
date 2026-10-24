"""Impose complete books across cut piles gathered from one full stack of sheets."""

from math import ceil

import pikepdf
from snackpress_imposition.geometry import Settings, calculate
from snackpress_imposition.pdf import PT

from .common import artifact, report, write_json


def cut_stack(count, per_book, poses):
    # Allocate complete books to each cut pile across the whole PDF. Restarting
    # this distribution in batches would interleave the books after one full cut.
    books_per_pose, extra = divmod(ceil(count / per_book), poses)
    starts, lengths, books = [], [], []
    first_book = 0
    for pose in range(poses):
        book_count = books_per_pose + (pose < extra)
        start = first_book * per_book
        stop = min(count, (first_book + book_count) * per_book)
        starts.append(start)
        lengths.append(max(0, stop - start))
        books.extend(
            {
                "pose": pose + 1,
                "first_index": book * per_book,
                "last_index": min((book + 1) * per_book, count) - 1,
            }
            for book in range(first_book, first_book + book_count)
        )
        first_book += book_count
    depth = max(lengths)
    sheets = [
        [
            start + level if level < length else None
            for start, length in zip(starts, lengths, strict=True)
        ]
        for level in range(depth)
    ]
    return sheets, [{"first_sheet": 1, "last_sheet": depth, "books": books}]


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
            bleed=params.bleed,
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
                    b = params.bleed * PT
                    form.BBox = pikepdf.Array([box[0] - b, box[1] - b, box[2] + b, box[3] + b])
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
    artifacts = [artifact(path, "Planche imposée pour coupe")]
    if not preview:

        def serial(index):
            if params.repiquages and not any(
                item.source == "sequence" for item in params.repiquages
            ):
                return f"Ligne CSV {index + 2}"
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
                **(
                    {
                        "csv_row_numbers": [
                            [i + 2 if i is not None else None for i in row] for row in sheets
                        ]
                    }
                    if params.csv_data
                    else {}
                ),
            },
        )
        cut_piles = {}
        for book in batches[0]["books"]:
            cut_piles.setdefault(book["pose"], []).append(book)
        instructions = folder / "fiche-souches.pdf"
        report(
            instructions,
            "Fortune Cookie — coupe en souches",
            [
                *metrics.items(),
                ("Grille", f"{plan.columns} colonnes × {plan.rows} lignes ; {plan.rotation}°"),
                *[
                    (
                        f"Pose {pose} · {len(books)} souche(s)",
                        f"{serial(books[0]['first_index'])} à {serial(books[-1]['last_index'])}",
                    )
                    for pose, books in cut_piles.items()
                ],
            ],
            "Imprimer à 100 %, dans l’ordre du PDF, première feuille au-dessus de la pile. "
            "Empiler toutes les feuilles ensemble et couper la pile suivant les repères, "
            "puis ramasser les poses de gauche à droite et de haut en bas. Diviser chaque pile "
            "découpée en souches du nombre de billets demandé. Les emplacements "
            "vides restent blancs ; la dernière souche peut être incomplète. "
            "Les repères du gabarit Pizza sont absents de l’export.",
        )
        artifacts += [
            artifact(instructions, "Plan de coupe"),
            artifact(manifest, "Ordre des billets et des souches JSON"),
            artifact(source, "Billets individuels sans imposition"),
        ]
    return artifacts, metrics, plan.warnings
