import json
from datetime import datetime, timedelta

import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import product_snapshot
from snackpress_tools.runner import run
from sqlalchemy.orm import Session
from test_api import api  # noqa: F401
from test_pdf_styles import assert_page_totals

# Pytest discovers the imported fixture.
# ruff: noqa: F811


@pytest.mark.parametrize("product_id", ["card", "leaflet", "brochure", "banner", "label", "ticket"])
def test_product_specifications_and_branding_on_every_page(tmp_path, product_id):
    snapshot = product_snapshot(product_id)
    notes = "\n".join(f"Consigne {i} : contrôler la fabrication." for i in range(70))
    run(
        tmp_path,
        "kebab",
        [],
        {
            "product_snapshot": snapshot,
            "quantity": 1200,
            "client": "Atelier Alice",
            "notes": notes,
        },
    )
    path = tmp_path / "fiche-fabrication.pdf"
    assert assert_page_totals(path) > 1
    with pdfium.PdfDocument(str(path)) as pdf:
        texts = [page.get_textpage().get_text_bounded() for page in pdf]
    for text in texts:
        assert "Date du rapport" in text and "snackpress.app" in text
    text = "\n".join(texts)
    assert snapshot["product_name"] in text
    assert "1200 exemplaires" in text and "Atelier Alice" in text
    assert "Consigne 69" in text
    for component in snapshot["variant"]["components"]:
        assert component["name"] in text
        assert f"{component['width']:g} × {component['height']:g} mm" in text
        for slot in component["slots"]:
            assert f"{slot['name']} : {slot['pages']} page(s)" in text
    for material in snapshot["materials"]:
        if any(c["material_id"] == material["id"] for c in snapshot["variant"]["components"]):
            assert material["name"] in text
    for finish in snapshot["finishes"]:
        if finish["id"] in snapshot["variant"]["finish_ids"]:
            assert finish["name"] in text
    with pikepdf.open(path) as pdf:
        assert all(
            any(a.get("/A", {}).get("/URI") == "https://snackpress.app" for a in page.Annots)
            for page in pdf.pages
        )
    saved = json.loads((tmp_path / "reglages.json").read_text())
    assert saved["settings"]["product_snapshot"] == snapshot


def test_kebab_requires_valid_product(api):
    client, _ = api
    assert client.post("/api/tools/kebab/run").status_code == 422
    snapshot = product_snapshot()
    snapshot["variant"]["components"][0]["material_id"] = "unknown"
    response = client.post(
        "/api/tools/kebab/run",
        data={
            "settings": json.dumps({"product_snapshot": snapshot}),
        },
    )
    assert response.status_code == 422


def test_shared_pdf_access_and_deletion(api):
    client, _ = api
    response = client.post(
        "/api/tools/kebab/run",
        data={
            "settings": json.dumps({"product_snapshot": product_snapshot()}),
        },
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    url = f"/api/tool-jobs/{job_id}/files/fiche-fabrication.pdf"
    client.cookies.clear()
    pdf = client.get(url)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"] == "application/pdf"
    assert client.get(f"/api/tool-jobs/{job_id}/files/tool-request.json").status_code == 404
    assert client.delete(f"/api/tool-jobs/{job_id}").status_code == 204
    assert client.get(url).status_code == 404


def test_shared_pdf_expires_after_24_hours(api):
    client, module = api
    response = client.post(
        "/api/tools/kebab/run",
        data={
            "settings": json.dumps({"product_snapshot": product_snapshot("brochure")}),
        },
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    with Session(module.engine) as db:
        db.get(module.Job, job_id).created_at = datetime.now() - timedelta(hours=25)
        db.commit()
    assert client.get(f"/api/tool-jobs/{job_id}/files/fiche-fabrication.pdf").status_code == 404
