import importlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from snackpress_api import accounts
from snackpress_api.database import AccountToken, Configuration, LoginSession, User
from sqlalchemy import select
from sqlalchemy.orm import Session

HEADERS = {"X-Snackpress-Request": "1", "Origin": "http://127.0.0.1:5173"}
PASSWORD = "Une longue phrase personnelle 2026"


@pytest.fixture
def account_api(tmp_path, monkeypatch):
    monkeypatch.setenv("SNACKPRESS_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("SNACKPRESS_PUBLIC_URL", "http://127.0.0.1:5173")
    accounts._rates.clear()
    deliveries = []
    monkeypatch.setattr(accounts, "send_mail", lambda *args: deliveries.append(args))
    import snackpress_api.main as module

    module = importlib.reload(module)
    with TestClient(module.app, headers=HEADERS) as client:
        yield client, module, deliveries


def activate(client, deliveries, email="alice@example.com"):
    response = client.post("/api/auth/register", json={"email": email})
    assert response.status_code == 200, response.text
    token = deliveries[-1][2]
    response = client.post("/api/auth/verify", json={"token": token, "password": PASSWORD})
    assert response.status_code == 200, response.text
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response


def create(client, tool="pizza", name="Cartes", settings=None, **kw):
    return client.post(
        f"/api/configurations?tool_id={tool}",
        json={
            "name": name,
            "settings": settings or {},
            **kw,
        },
    )


def body(config, **patch):
    return {
        key: patch.get(key, config[key])
        for key in ("name", "settings", "schema_version", "revision", "is_default")
    }


def test_activation_cookie_password_storage_and_logout(account_api):
    client, module, deliveries = account_api
    assert client.get("/api/auth/me").status_code == 401
    response = activate(client, deliveries)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/auth/me").json()["email"] == "alice@example.com"
    with Session(module.engine) as db:
        user = db.scalar(select(User))
        assert user.verified and user.password_hash.startswith("scrypt$")
        assert PASSWORD not in user.password_hash
        session = db.scalar(select(LoginSession))
        assert session.token_hash != client.cookies.get(accounts.COOKIE)
        assert db.scalar(select(AccountToken)) is None
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "alice@example.com", "password": "incorrect"}
        ).status_code
        == 401
    )
    assert client.get("/api/tools").status_code == 200


def test_csrf_input_limits_and_generic_responses(account_api):
    client, _, deliveries = account_api
    assert client.post("/api/auth/register", json={"email": "bad"}).status_code == 422
    assert (
        client.post(
            "/api/auth/register",
            json={"email": "alice@example.com"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    response = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com"},
        headers={"X-Snackpress-Request": ""},
    )
    assert response.status_code == 403 and not deliveries
    assert (
        client.post(
            "/api/auth/login",
            json={
                "email": "alice@example.com",
                "password": "s" * 90000,
            },
        ).status_code
        == 413
    )
    response = client.post("/api/auth/verify", json={"token": "a" * 32, "password": "secret"})
    assert response.status_code == 422 and "secret" not in response.text
    activate(client, deliveries)
    first = client.post("/api/auth/register", json={"email": "alice@example.com"})
    second = client.post("/api/auth/register", json={"email": "bob@example.com"})
    assert first.json() == second.json()


def test_links_one_use_expiration_and_reset_revokes_sessions(account_api):
    client, module, deliveries = account_api
    activate(client, deliveries)
    original = deliveries[0][2]
    assert (
        client.post("/api/auth/verify", json={"token": original, "password": PASSWORD}).status_code
        == 400
    )
    before = len(deliveries)
    unknown = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert len(deliveries) == before
    known = client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    assert unknown.json() == known.json()
    reset_token = deliveries[-1][2]
    with Session(module.engine) as db:
        token = db.get(AccountToken, accounts.digest(reset_token))
        token.expires_at = accounts.now() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post(
            "/api/auth/reset-password", json={"token": reset_token, "password": PASSWORD}
        ).status_code
        == 400
    )
    client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": deliveries[-1][2], "password": PASSWORD + " nouveau"},
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": PASSWORD + " nouveau"},
        ).status_code
        == 200
    )


def test_sushi_configurations_preserve_lines_and_convert_legacy_creases(account_api):
    client, _, deliveries = account_api
    activate(client, deliveries)
    response = create(client, tool="sushi", settings={"shape": "rectangle", "creases": "20,60"})
    assert response.status_code == 201, response.text
    original = response.json()
    assert original["settings"]["lines"] == [
        {"kind": "crease", "axis": "vertical", "position": 20},
        {"kind": "crease", "axis": "vertical", "position": 60},
    ]
    assert "creases" not in original["settings"]
    settings = {
        **original["settings"],
        "bleed": 3,
        "shape": "none",
        "lines": '[{"kind":"cut","axis":"horizontal","position":15}]',
    }
    response = client.put(
        f"/api/configurations/{original['id']}", json=body(original, settings=settings)
    )
    assert response.status_code == 200, response.text
    saved = client.get("/api/configurations?tool_id=sushi").json()[0]["settings"]
    assert saved["bleed"] == 3 and saved["shape"] == "none"
    assert saved["lines"] == [{"kind": "cut", "axis": "horizontal", "position": 15}]


def test_configurations_ownership_defaults_conflicts_and_persistence(account_api):
    client, module, deliveries = account_api
    assert create(client).status_code == 401
    activate(client, deliveries)
    assert (
        client.post(
            "/api/configurations?tool_id=pizza",
            headers={"X-Snackpress-Account": "another-account"},
            json={"name": "Private", "settings": {}},
        ).status_code
        == 409
    )
    first = create(client, is_default=True).json()
    second_response = create(client, name="Autre presse", is_default=True)
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    listing = client.get("/api/configurations?tool_id=pizza").json()
    assert [item["id"] for item in listing if item["is_default"]] == [second["id"]]
    assert create(client).status_code == 409
    # Setting another default bumped the old one's revision.
    assert client.put(f"/api/configurations/{first['id']}", json=body(first)).status_code == 409
    updated = client.put(
        f"/api/configurations/{second['id']}",
        json=body(second, name="Nouvelle presse", settings={"width": 100}),
    )
    assert updated.status_code == 200, updated.text
    second = updated.json()
    assert second["revision"] == 2 and second["settings"]["width"] == 100
    # Unrelated tools and users must not replace this default.
    create(client, tool="taco", is_default=True)
    original_cookie = client.cookies.get(accounts.COOKIE)
    client.post("/api/auth/logout")
    activate(client, deliveries, "bob@example.com")
    assert client.get("/api/configurations?tool_id=pizza").json() == []
    assert client.put(f"/api/configurations/{second['id']}", json=body(second)).status_code == 404
    assert client.delete(f"/api/configurations/{second['id']}?revision=2").status_code == 404
    create(client, name="Cartes", is_default=True)
    client.post("/api/auth/logout")
    assert original_cookie != client.cookies.get(accounts.COOKIE)
    client.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    # A fresh connection to the same SQLite file sees saved data after job purging.
    module.purge()
    with Session(module.engine) as db:
        assert db.get(Configuration, second["id"]).name == "Nouvelle presse"
    assert client.delete(f"/api/configurations/{second['id']}?revision=1").status_code == 409
    assert client.delete(f"/api/configurations/{second['id']}?revision=2").status_code == 204


def test_validation_all_tools_and_numbering_roundtrip(account_api):
    from conftest import product_snapshot
    from snackpress_tools.catalog import MODELS

    client, _, deliveries = account_api
    activate(client, deliveries)
    for tool in [*MODELS, "imposition"]:
        settings = {"product_snapshot": product_snapshot()} if tool == "kebab" else {}
        response = create(client, tool=tool, settings=settings)
        assert response.status_code == 201, (tool, response.text)
    assert create(client, tool="unknown").status_code == 404
    assert create(client, name=" ").status_code == 422
    assert create(client, settings={"files": ["private.pdf"]}).status_code == 422
    assert create(client, settings={"width": -1}).status_code == 422
    assert create(client, schema_version=2).status_code == 422
    response = create(client, tool="imposition", name="Imposition", settings={"confirm_trim": True})
    assert response.json()["settings"]["confirm_trim"] is False
    numberings = [
        {"x": 20, "y": 30, "font": "Courier", "color": "#aabbcc", "size": 14, "rotation": 90}
    ]
    response = create(
        client,
        tool="fortune-cookie",
        name="Billets",
        settings={
            "numberings": numberings,
            "prefix": "B-",
            "pizza_template": {"shape": "ellipse"},
            "layer_template": {"sheet_width": 210, "sheet_height": 150},
            "tickets_per_book": 20,
        },
    )
    assert response.status_code == 201, response.text
    saved = response.json()["settings"]["repiquages"]
    assert [
        {key: item[key] for key in original}
        for item, original in zip(saved, numberings, strict=True)
    ] == numberings
    assert saved[0]["align"] == "left"
    assert response.json()["settings"]["pizza_template"]["shape"] == "ellipse"
    assert response.json()["settings"]["layer_template"]["sheet_width"] == 210
    assert response.json()["settings"]["tickets_per_book"] == 20


def test_rate_limit_and_expired_session(account_api):
    client, module, deliveries = account_api
    activate(client, deliveries)
    with Session(module.engine) as db:
        db.scalar(select(LoginSession)).expires_at = accounts.now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/configurations?tool_id=pizza").status_code == 401
    accounts._rates.clear()
    for _ in range(12):
        assert (
            client.post(
                "/api/auth/forgot-password", json={"email": "nobody@example.com"}
            ).status_code
            == 200
        )
    assert (
        client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).status_code
        == 429
    )


def test_fortune_configuration_preserves_csv_sources_and_alignments(account_api):
    client, _, deliveries = account_api
    activate(client, deliveries)
    data = {"columns": ["nom", "reference"], "rows": [["Élodie " + "A" * 800, "00017"]] * 100}
    response = create(
        client,
        tool="fortune-cookie",
        name="Invitations",
        settings={
            "count": 100,
            "csv_data": data,
            "repiquages": [
                {"source": "csv", "column": "nom", "align": "center", "x": 42},
                {
                    "source": "csv",
                    "column": "reference",
                    "rendering": "code128",
                    "align": "right",
                    "x": 80,
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    saved = client.get("/api/configurations?tool_id=fortune-cookie").json()[0]["settings"]
    assert saved["csv_data"] == data
    assert saved["repiquages"][0]["align"] == "center"
    assert saved["repiquages"][1]["rendering"] == "code128"
    assert saved["repiquages"][1]["column"] == "reference"


def test_smtp_unavailable_rolls_back_registration(account_api, monkeypatch):
    client, module, _ = account_api

    def unavailable(*_):
        from fastapi import HTTPException

        raise HTTPException(503, "E-mail non envoyé.")

    monkeypatch.setattr(accounts, "send_mail", unavailable)
    assert client.post("/api/auth/register", json={"email": "alice@example.com"}).status_code == 503
    with Session(module.engine) as db:
        assert db.scalar(select(User)) is None
        assert db.scalar(select(AccountToken)) is None


def test_production_cookie_is_secure_and_email_is_normalized(account_api, monkeypatch):
    client, _, deliveries = account_api
    activate(client, deliveries, "ALICE@EXAMPLE.COM")
    assert client.get("/api/auth/me").json()["email"] == "alice@example.com"
    monkeypatch.setenv("SNACKPRESS_PUBLIC_URL", "https://snackpress.example.com")
    response = client.post(
        "/api/auth/login",
        headers={"Origin": "https://snackpress.example.com"},
        json={"email": "alice@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    assert "; Secure" in response.headers["set-cookie"]


def test_local_email_transport_is_private_and_rejects_remote_origins(account_api, monkeypatch):
    from pathlib import Path

    client, module, _ = account_api
    # Exercise the real file transport, never an external SMTP server.
    real_send = importlib.reload(accounts).send_mail
    monkeypatch.setattr(accounts, "send_mail", real_send)
    monkeypatch.setenv("SNACKPRESS_MAIL_MODE", "file")
    response = client.post("/api/auth/register", json={"email": "alice@example.com"})
    assert response.status_code == 200, response.text
    mails = list((module.DATA / "mail-outbox").glob("*.eml"))
    assert len(mails) == 1 and mails[0].stat().st_mode & 0o777 == 0o600
    from email import policy
    from email.parser import Parser

    mail = Parser(policy=policy.default).parsestr(Path(mails[0]).read_text())
    assert "http://127.0.0.1:5173/#account=verify&token=" in mail.get_content()
    module.purge()
    assert mails[0].exists()
    monkeypatch.setenv("SNACKPRESS_PUBLIC_URL", "https://snackpress.example.com")
    with pytest.raises(Exception) as exc:
        real_send("alice@example.com", "verify", "token")
    assert exc.value.status_code == 503
