from copy import deepcopy

from test_accounts import account_api, activate  # noqa: F401

# Pytest discovers the imported fixture.
# ruff: noqa: F811


def test_catalog_auth_isolation_revision_validation_and_persistence(account_api):
    client, module, deliveries = account_api
    starter = client.get("/api/print-catalog/starter")
    assert starter.status_code == 200
    assert len(starter.json()["catalog"]["products"]) == 6
    assert client.get("/api/print-catalog").status_code == 401
    assert client.put("/api/print-catalog", json=starter.json()).status_code == 401
    activate(client, deliveries)
    account = client.get("/api/auth/me").json()["id"]
    original = client.get("/api/print-catalog").json()
    changed = deepcopy(original)
    changed["catalog"]["products"][0]["name"] = "Carte atelier Alice"
    changed["catalog"]["finishes"][0]["appearance"] = {
        "mode": "path",
        "color": "#123456",
        "dash_color": "#654321",
        "alpha": 0.25,
        "gradient": True,
        "end_color": "#abcdef",
        "angle": 45,
    }
    response = client.put(
        "/api/print-catalog", json=changed, headers={"X-Snackpress-Account": account}
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["revision"] == 1
    assert (
        saved["catalog"]["finishes"][0]["appearance"]
        == (changed["catalog"]["finishes"][0]["appearance"])
    )
    assert response.headers["cache-control"] == "no-store"
    assert client.put("/api/print-catalog", json=changed).status_code == 409
    assert (
        client.put(
            "/api/print-catalog", json=saved, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/api/print-catalog", json=saved, headers={"X-Snackpress-Request": ""}
        ).status_code
        == 403
    )
    bad = deepcopy(saved)
    bad["catalog"]["products"][0]["category_id"] = "missing"
    assert client.put("/api/print-catalog", json=bad).status_code == 422
    assert client.get("/api/print-catalog").json() == saved
    assert client.get("/api/print-catalog/starter").json() == original
    client.post("/api/auth/logout")
    activate(client, deliveries, "bob@example.com")
    assert client.get("/api/print-catalog").json() == original
    assert (
        client.get("/api/print-catalog", headers={"X-Snackpress-Account": account}).status_code
        == 409
    )
    client.post("/api/auth/logout")
    activate_login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "Une longue phrase personnelle 2026"},
    )
    assert activate_login.status_code == 200
    module.purge()
    assert client.get("/api/print-catalog").json() == saved


def test_catalog_request_size_bound(account_api):
    client, _, deliveries = account_api
    activate(client, deliveries)
    response = client.put("/api/print-catalog", content="x" * 310000)
    assert response.status_code == 413
