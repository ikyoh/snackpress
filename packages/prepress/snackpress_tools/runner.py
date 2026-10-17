from pathlib import Path

from . import documents as d
from . import generators as g
from .catalog import CATALOG, MODELS
from .common import artifact, write_json

HANDLERS = dict(
    zip(
        CATALOG,
        [
            g.burger,
            d.chili,
            d.donut,
            d.tiramisu,
            g.taco,
            g.pizza,
            g.burrito,
            g.club,
            g.fortune,
            d.poke,
            g.sushi,
            g.kebab,
            d.layer,
            d.bento,
        ],
        strict=True,
    )
)


def run(folder: Path, tool: str, files: list[Path], values: dict, *, preview=False):
    if tool not in CATALOG:
        raise ValueError("Outil inconnu.")
    definition = CATALOG[tool]
    if not definition.min_files <= len(files) <= definition.max_files:
        raise ValueError(
            f"Cet outil accepte {definition.min_files} à {definition.max_files} fichier(s)."
        )
    if any(f.suffix != ".pdf" for f in files) and tool != "donut":
        raise ValueError("Cet outil accepte uniquement les PDF.")
    params = MODELS[tool].model_validate(values)
    if tool == "burger" and params.product_snapshot is not None:
        from .product_proof import generate_product

        result = generate_product(folder, files, params, preview=preview)
    else:
        result = HANDLERS[tool](folder, files, params)
    result.warnings.insert(0, definition.limit)
    settings = folder / "reglages.json"
    write_json(
        settings,
        {
            "tool": tool,
            "settings": params.model_dump(),
            "metrics": result.metrics,
            "warnings": result.warnings,
        },
    )
    result.artifacts.append(artifact(settings, "Réglages et limites JSON"))
    write_json(folder / "result.json", result.model_dump())
    return result
