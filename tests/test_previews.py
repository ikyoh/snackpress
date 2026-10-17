import importlib
import json
from datetime import datetime, timedelta

import pikepdf
import pytest
from fastapi.testclient import TestClient
from snackpress_tools.catalog import CATALOG
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SNACKPRESS_DATA", str(tmp_path / "data"))
    import snackpress_api.main as module

    module = importlib.reload(module)
    with TestClient(module.app) as client:
        yield client, module


def session(client, tool, source=None):
    files = [("files", ("source.pdf", source.read_bytes()))] if source else []
    response = client.post(f"/api/tools/{tool}/previews", files=files)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def render(client, preview_id, settings=None):
    return client.post(f"/api/tool-previews/{preview_id}/render", json={"settings": settings or {}})


@pytest.mark.parametrize("tool", list(CATALOG))
def test_all_tool_previews_are_readable_and_separate_from_final_jobs(api, source, tool):
    client, module = api
    files = [("files", ("source.pdf", source.read_bytes()))] * CATALOG[tool].min_files
    response = client.post(f"/api/tools/{tool}/previews", files=files)
    assert response.status_code == 201, response.text
    preview_id = response.json()["id"]
    response = render(client, preview_id)
    assert response.status_code == 200, (tool, response.text)
    data = response.json()
    assert data["artifacts"] and data["notice"]
    assert all(a["media_type"] in {"application/pdf", "image/png"} for a in data["artifacts"])
    artifact = data["artifacts"][0]
    url = f"/api/tool-previews/{preview_id}/{data['generation']}/files/{artifact['name']}"
    download = client.get(url)
    assert download.status_code == 200 and download.content.startswith(b"%PDF")
    assert download.headers["cache-control"] == "no-store"
    assert client.get(f"/api/tool-jobs/{preview_id}").status_code == 404
    assert client.get(f"/api/jobs/{preview_id}/source").status_code == 404
    assert client.delete(f"/api/tool-previews/{preview_id}").status_code == 204
    assert not (module.DATA / preview_id).exists()


def test_repeated_previews_reuse_inputs_bound_storage_and_preserve_previous_on_error(api):
    client, module = api
    preview_id = session(client, "pizza")
    first = render(client, preview_id, {"shape": "ellipse", "width": 100, "height": 60}).json()
    for width in (110, 120):
        assert render(client, preview_id, {"width": width}).status_code == 200
    url = f"/api/tool-previews/{preview_id}/{first['generation']}/files/gabarit.pdf"
    assert client.get(url).status_code == 200
    assert render(client, preview_id, {"width": -1}).status_code == 422
    assert client.get(url).status_code == 200
    assert render(client, preview_id, {"width": 130}).status_code == 200
    assert client.get(url).status_code == 404
    assert len([p for p in (module.DATA / preview_id).iterdir() if p.is_dir()]) == 3
    with Session(module.engine) as db:
        assert len(list(db.scalars(select(module.Job)))) == 1
    assert client.get(f"/api/tool-previews/{preview_id}/../files/input-0.pdf").status_code == 404


def test_expiry_busy_and_invalid_import_cleanup(api, source):
    client, module = api
    assert client.post("/api/tools/unknown/previews").status_code == 404
    assert client.post("/api/tools/tiramisu/previews").status_code == 422
    assert (
        client.post(
            "/api/tools/donut/previews", files={"files": ("fake.pdf", b"not a PDF")}
        ).status_code
        == 422
    )
    assert not [p for p in module.DATA.iterdir() if p.is_dir()]
    preview_id = session(client, "donut", source)
    module.busy.add(preview_id)
    assert render(client, preview_id).status_code == 409
    assert client.delete(f"/api/tool-previews/{preview_id}").status_code == 409
    module.busy.discard(preview_id)
    with Session(module.engine) as db:
        db.get(module.Job, preview_id).created_at = datetime.now() - timedelta(minutes=31)
        db.commit()
    assert render(client, preview_id).status_code == 404
    module.purge()
    assert not (module.DATA / preview_id).exists()


def test_light_preview_does_not_change_full_resolution_or_count(api, source):
    client, module = api
    preview_id = session(client, "fortune-cookie")
    data = render(client, preview_id, {"count": 20}).json()
    assert data["artifacts"][0]["pages"] == 2
    final = client.post("/api/tools/fortune-cookie/run", data={"settings": '{"count":20}'})
    assert final.status_code == 201
    assert final.json()["artifacts"][0]["pages"] == 20
    preview_id = session(client, "donut", source)
    data = render(client, preview_id, {"dpi": 300}).json()
    assert data["metrics"]["Résolution (dpi)"] == 96
    root = module.DATA / preview_id
    manifest = json.loads((root / data["generation"] / "tool-request.json").read_text())
    assert manifest["settings"]["dpi"] == 300
    assert (root / "input-0.pdf").exists()
    # Read-only publication excludes source files and settings JSON.
    for name in ("tool-request.json", "input-0.pdf", "reglages.json"):
        assert (
            client.get(
                f"/api/tool-previews/{preview_id}/{data['generation']}/files/{name}"
            ).status_code
            == 404
        )


def test_imposition_preview_reuses_source_and_never_exports_final_implicitly(api, source):
    client, module = api
    job = client.post("/api/jobs", files={"file": ("card.pdf", source.read_bytes())}).json()
    created = client.post("/api/tools/imposition/previews", data={"source_job_id": job["id"]})
    assert created.status_code == 201, created.text
    preview_id = created.json()["id"]
    data = render(client, preview_id).json()
    assert data["artifacts"][0]["pages"] == 2
    assert not (module.DATA / job["id"] / "output.pdf").exists()
    with pikepdf.open(module.DATA / preview_id / data["generation"] / "apercu.pdf") as pdf:
        assert float(pdf.pages[0].mediabox[2]) * 25.4 / 72 == pytest.approx(320)


def test_disconnected_preview_cancels_worker(api, monkeypatch, tmp_path):
    import asyncio

    from fastapi import HTTPException
    from snackpress_api.previews import disconnected_worker

    _, module = api
    stopped = []

    async def pending_worker(*_):
        try:
            await asyncio.sleep(60)
        finally:
            stopped.append(True)

    class Disconnected:
        async def is_disconnected(self):
            return True

    monkeypatch.setattr(module, "worker", pending_worker)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(disconnected_worker(Disconnected(), "tool-preview", tmp_path))
    assert exc.value.status_code == 499
    assert stopped == [True]
