"""One disposable process per PDF operation. No client content is written to logs."""

import json
import resource
import sys
from pathlib import Path

from snackpress_imposition.geometry import Plan
from snackpress_imposition.pdf import compose, inspect

resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
resource.setrlimit(resource.RLIMIT_FSIZE, (150 * 1024 * 1024, 150 * 1024 * 1024))
# RLIMIT_AS is not supported reliably by macOS; enforce it on the Linux deployment target.
if sys.platform == "linux":
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
try:
    action, folder = sys.argv[1], Path(sys.argv[2])
    if action == "inspect":
        result = inspect(folder / "source.pdf").model_dump()
    elif action in {"tools", "tool-preview"}:
        from snackpress_tools.runner import run

        if action == "tool-preview":
            from snackpress_tools.preview import render as run

        request = json.loads((folder / "tool-request.json").read_text())
        result = run(
            folder,
            request["tool"],
            [folder / name for name in request["files"]],
            request["settings"],
        ).model_dump()
    else:
        plan = Plan.model_validate_json((folder / "request.json").read_text())
        compose(folder / "source.pdf", folder / "output.tmp", plan)
        (folder / "output.tmp").replace(folder / "output.pdf")
        (folder / "request.json").replace(folder / "plan.json")
        result = {"ok": True}
    print(json.dumps(result))
except Exception as exc:
    print(
        json.dumps(
            {
                "error": str(exc)
                if isinstance(exc, ValueError)
                else "Le traitement PDF a échoué. Réexportez le fichier source."
            }
        )
    )
    sys.exit(1)
