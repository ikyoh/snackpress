import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = [str(root / "apps/api"), str(root / "packages/imposition"), str(root / "packages/prepress")]
os.environ["PYTHONPATH"] = os.pathsep.join(paths)
sys.path[:0] = paths
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "snackpress_api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[
            str(root / "apps/api"),
            str(root / "packages/imposition"),
            str(root / "packages/prepress"),
        ],
    )
