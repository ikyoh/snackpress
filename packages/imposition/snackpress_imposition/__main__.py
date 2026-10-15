import argparse
from pathlib import Path

from .geometry import Settings, calculate
from .pdf import compose, inspect

parser = argparse.ArgumentParser(description="Snackpress : imposition PDF à 100 %")
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path, nargs="?")
parser.add_argument("--settings", type=Path)
args = parser.parse_args()
info = inspect(args.source)
if not args.output:
    print(info.model_dump_json(indent=2))
else:
    settings = (
        Settings.model_validate_json(args.settings.read_text())
        if args.settings
        else Settings(
            trim_width=info.pages[0].width, trim_height=info.pages[0].height, confirm_trim=True
        )
    )
    plan = calculate(settings, len(info.pages) == 2)
    compose(args.source, args.output, plan)
    args.output.with_suffix(".json").write_text(plan.model_dump_json(indent=2))
