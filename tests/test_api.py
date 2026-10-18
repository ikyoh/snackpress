import importlib
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SNACKPRESS_DATA", str(tmp_path / "data"))
    import snackpress_api.main as module

    module = importlib.reload(module)
    with TestClient(module.app) as client:
        yield client, module


def test_complete_workflow_and_deletion(api, source):
    client, module = api
    response = client.post("/api/jobs", files={"file": ("card.pdf", source.read_bytes())})
    assert response.status_code == 201, response.text
    job = response.json()
    assert len(job["document"]["pages"]) == 2
    url = f"/api/jobs/{job['id']}"
    plan = client.post(f"{url}/plan", json={})
    assert plan.status_code == 200
    assert plan.json()["poses"] == 21
    export = client.post(f"{url}/export", json={})
    assert export.status_code == 200, export.text
    assert client.get(f"{url}/output").content.startswith(b"%PDF")
    assert client.get(f"{url}/settings").json()["sheets"] == 12
    assert client.get(f"{url}/source").headers["cache-control"] == "no-store"
    assert client.delete(url).status_code == 204
    assert not (module.DATA / job["id"]).exists()
    assert client.get(f"{url}/source").status_code == 404


def test_invalid_and_oversized_uploads(api, monkeypatch):
    client, module = api
    assert client.post("/api/jobs", files={"file": ("fake.pdf", b"hello")}).status_code == 422
    monkeypatch.setattr(module, "MAX_BYTES", 10)
    assert (
        client.post("/api/jobs", files={"file": ("big.pdf", b"%PDF-" + b"x" * 20)}).status_code
        == 413
    )
    assert not [p for p in module.DATA.iterdir() if p.is_dir()]


def test_expiration_removes_files(api, source):
    client, module = api
    job = client.post("/api/jobs", files={"file": ("card.pdf", source.read_bytes())}).json()
    with Session(module.engine) as db:
        db.get(module.Job, job["id"]).created_at = datetime.now() - timedelta(hours=25)
        db.commit()
    assert client.get(f"/api/jobs/{job['id']}/source").status_code == 404
    module.purge()
    assert not (module.DATA / job["id"]).exists()


def test_failed_regeneration_keeps_previous_export_consistent(api, source):
    client, _ = api
    job = client.post("/api/jobs", files={"file": ("card.pdf", source.read_bytes())}).json()
    url = f"/api/jobs/{job['id']}"
    assert client.post(f"{url}/export", json={}).status_code == 200
    previous = client.get(f"{url}/settings").json()
    assert client.post(f"{url}/export", json={"trim_width": 90}).status_code == 422
    assert client.get(f"{url}/settings").json() == previous
    assert client.get(f"{url}/output").content.startswith(b"%PDF")


def test_tools_catalog_validation_generation_and_delete(api):
    client, module = api
    response = client.get("/api/tools")
    assert response.status_code == 200
    assert len(response.json()) == 14
    result = client.post("/api/tools/pizza/run", data={"settings": '{"width":85,"height":55}'})
    assert result.status_code == 201, result.text
    data = result.json()
    assert data["tool"] == "pizza"
    url = f"/api/tool-jobs/{data['id']}"
    assert client.get(f"{url}/files/gabarit.pdf").content.startswith(b"%PDF")
    assert client.get(f"{url}/files/source.pdf").status_code == 404
    assert client.get(f"/api/jobs/{data['id']}/source").status_code == 404
    assert client.delete(url).status_code == 204
    assert client.get(f"{url}/files/gabarit.pdf").status_code == 404
    assert not (module.DATA / data["id"]).exists()
    assert (
        client.post("/api/tools/fortune-cookie/run", data={"settings": '{"count":101}'}).status_code
        == 422
    )
    assert client.post("/api/tools/tiramisu/run").status_code == 422


def test_burger_example_matches_current_template_and_can_be_loaded(api):
    client, module = api
    settings = json.dumps(
        {"template_tool": "taco", "template_settings": {"width": 420, "height": 180}}
    )
    response = client.post("/api/tools/burger/example", data={"settings": settings})
    assert response.status_code == 201, response.text
    example = response.json()
    url = f"/api/tool-jobs/{example['id']}"
    files = [
        ("files", (a["name"], client.get(f"{url}/files/{a['name']}").content))
        for a in example["artifacts"]
    ]
    proof = client.post("/api/tools/burger/run", data={"settings": settings}, files=files)
    assert proof.status_code == 201, proof.text
    assert proof.json()["metrics"]["Faces"] == 2
    assert client.delete(url).status_code == 204
    assert not (module.DATA / example["id"]).exists()
    assert (
        client.post(
            "/api/tools/burger/example", data={"settings": '{"template_tool":"pdf"}'}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/tools/burger/example",
            data={"settings": '{"template_tool":"taco","template_settings":{"width":0}}'},
        ).status_code
        == 422
    )


def test_tools_pdf_processing_and_failed_import_cleanup(api, source):
    client, module = api
    result = client.post(
        "/api/tools/chili-dog/run",
        data={"settings": "{}"},
        files=[("files", ("source.pdf", source.read_bytes()))],
    )
    assert result.status_code == 201, result.text
    data = result.json()
    assert data["metrics"]["Pages"] == 2
    before = set(module.DATA.iterdir())
    failed = client.post(
        "/api/tools/chili-dog/run",
        data={"settings": "{}"},
        files=[("files", ("source.pdf", b"%PDF-invalid"))],
    )
    assert failed.status_code == 422
    assert set(module.DATA.iterdir()) == before
