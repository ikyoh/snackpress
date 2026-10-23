"""Bound expensive work for interactive previews; leave final settings untouched."""

from pathlib import Path

import pikepdf

from .catalog import ToolResult
from .common import artifact, open_pdf
from .runner import run


def render(folder: Path, tool: str, files: list[Path], values: dict):
    if tool == "imposition":
        from snackpress_imposition.geometry import Settings, calculate
        from snackpress_imposition.pdf import compose, inspect

        # This confirmation only permits a disposable preview; final export still
        # requires the user to confirm dimensions in the original settings.
        params = Settings.model_validate({**values, "confirm_trim": True})
        info = inspect(files[0])
        plan = calculate(params, len(info.pages) == 2)
        target = folder / "apercu.pdf"
        compose(files[0], target, plan)
        return ToolResult(
            tool=tool,
            summary="Aperçu PDF de la planche.",
            artifacts=[artifact(target, "Planche de contrôle")],
        )
    settings = dict(values)
    sources = list(files)
    if tool in {"donut", "tiramisu", "poke"}:
        settings["dpi"] = min(int(settings.get("dpi", 96)), 96)
        for index, source in enumerate(files):
            if source.suffix == ".pdf":
                with open_pdf(source) as pdf:
                    sample = pikepdf.Pdf.new()
                    sample.pages.extend(list(pdf.pages)[:2])
                    target = folder / f"sample-{index}.pdf"
                    sample.save(target)
                    sources[index] = target
    if tool == "fortune-cookie":
        settings["count"] = min(int(settings.get("count", 10)), 2)
        settings["layer_template"] = None
    return run(folder, tool, sources, settings, preview=True)
