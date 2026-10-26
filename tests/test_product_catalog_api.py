from copy import deepcopy

import pytest
from test_accounts import account_api, activate  # noqa: F401

# Pytest discovers the imported fixture.
# ruff: noqa: F811


@pytest.mark.parametrize(
    "gradient_stops",
    [
        None,
        [
            {"color": "#ff0000", "position": 12},
            {"color": "#00ff00", "position": 47},
            {"color": "#0000ff", "position": 83},
        ],
    ],
)
def test_catalog_auth_isolation_revision_validation_and_persistence(account_api, gradient_stops):
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
        "diameter": 5,
        "width": 10,
        "height": 2,
        "color": "#123456",
        "dash_color": "#654321",
        "alpha": 0.25,
        "gradient": True,
        "end_color": "#abcdef",
        "gradient_stops": gradient_stops,
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


@pytest.mark.parametrize("mode", ["circle", "rectangle"])
def test_shape_occurrences_are_persisted_and_invalid_positions_rejected(account_api, mode):
    client, _, deliveries = account_api
    activate(client, deliveries)
    library = client.get("/api/print-catalog").json()
    finish = next(f for f in library["catalog"]["finishes"] if f["id"] == "perforation")
    finish["appearance"].update(mode=mode, diameter=6, width=8, height=4)
    # The seeded ticket already selects this finish; give it two occurrences.
    product = next(p for p in library["catalog"]["products"] if p["id"] == "ticket")
    product["variants"][0]["finish_placements"] = [
        {"finish_id": "perforation", "component_id": "ticket", "x": x, "y": 10, "page": 1}
        for x in (5, 100)
    ]
    response = client.put("/api/print-catalog", json=library)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert client.get("/api/print-catalog").json() == saved
    frozen = next(p for p in saved["catalog"]["products"] if p["id"] == "ticket")
    assert frozen["variants"][0]["finish_placements"] == product["variants"][0]["finish_placements"]
    frozen["variants"][0]["finish_placements"][1]["x"] = 149
    assert client.put("/api/print-catalog", json=saved).status_code == 422
    persisted = client.get("/api/print-catalog").json()
    assert persisted["revision"] == 1
