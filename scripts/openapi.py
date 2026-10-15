import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(root / "apps/api"),
    str(root / "packages/imposition"),
    str(root / "packages/prepress"),
]
from snackpress_api.main import app  # noqa: E402

(root / "packages/api-client/openapi.json").write_text(json.dumps(app.openapi(), indent=2))
