"""A-01/A-05: workspace Ghost hanya dapat diakses setelah PIN diverifikasi (token sesi server-side)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base, GlobalSetting, Thread
from main import app
from services import pin as pin_mod


@pytest.fixture
def dual(monkeypatch):
    def make():
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=eng)
        return sessionmaker(autocommit=False, autoflush=False, bind=eng)

    main_s, ghost_s = make(), make()
    with main_s() as s:
        s.add(Thread(title="Buku Utama", source_type="manual"))
        s.add(GlobalSetting(ghost_pin="12345"))
        s.commit()
    with ghost_s() as s:
        s.add(Thread(title="RAHASIA-GHOST", source_type="manual"))
        s.commit()
    monkeypatch.setattr("database.SessionLocalMain", main_s)
    monkeypatch.setattr("database.SessionLocalGhost", ghost_s)
    monkeypatch.setattr("database.get_session_factory", lambda ws="main": ghost_s if str(ws).lower() == "ghost" else main_s)
    monkeypatch.setattr("routers.system.switch_workspace", lambda target: None)
    pin_mod._failures.clear()
    database._ghost_sessions.clear()
    yield {"main": main_s, "ghost": ghost_s}
    pin_mod._failures.clear()
    database._ghost_sessions.clear()


def _titles(client, **kw):
    return [t["title"] for t in client.get("/api/threads", **kw).json()]


def test_header_alone_cannot_read_ghost(dual):
    client = TestClient(app)
    titles = _titles(client, headers={"X-Workspace": "ghost"})
    assert "RAHASIA-GHOST" not in titles
    assert "Buku Utama" in titles


def test_forged_workspace_cookie_cannot_read_ghost(dual):
    client = TestClient(app)
    client.cookies.set("readomni_workspace", "ghost")
    client.cookies.set(database.GHOST_SESSION_COOKIE, "token-palsu")
    assert "RAHASIA-GHOST" not in _titles(client)


def test_correct_pin_issues_session_that_unlocks_ghost(dual):
    client = TestClient(app)
    resp = client.post("/api/system/workspace", json={"workspace": "ghost", "pin": "12345"})
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert database.GHOST_SESSION_COOKIE in set_cookie and "HttpOnly" in set_cookie
    assert "RAHASIA-GHOST" in _titles(client, headers={"X-Workspace": "ghost"})


def test_wrong_pin_rejected_and_no_session(dual):
    client = TestClient(app)
    assert client.post("/api/system/workspace", json={"workspace": "ghost", "pin": "00000"}).status_code == 401
    assert "RAHASIA-GHOST" not in _titles(client, headers={"X-Workspace": "ghost"})


def test_lockout_after_repeated_failures(dual):
    client = TestClient(app)
    for _ in range(pin_mod.MAX_PIN_FAILURES):
        client.post("/api/system/workspace", json={"workspace": "ghost", "pin": "bad"})
    resp = client.post("/api/system/workspace", json={"workspace": "ghost", "pin": "12345"})
    assert resp.status_code == 429


def test_plaintext_pin_is_migrated_to_hash_on_success(dual):
    client = TestClient(app)
    client.post("/api/system/workspace", json={"workspace": "ghost", "pin": "12345"})
    with dual["main"]() as s:
        stored = s.query(GlobalSetting).first().ghost_pin
    assert pin_mod.is_hashed(stored) and pin_mod.verify_pin(stored, "12345")


def test_switch_back_to_main_revokes_session(dual):
    client = TestClient(app)
    client.post("/api/system/workspace", json={"workspace": "ghost", "pin": "12345"})
    token = client.cookies.get(database.GHOST_SESSION_COOKIE)
    client.post("/api/system/workspace", json={"workspace": "main", "pin": "12345"})
    assert token not in database._ghost_sessions


def test_changing_pin_requires_current_pin(dual):
    client = TestClient(app)
    assert client.post("/api/settings", json={"ghost_pin": "99999"}).status_code == 403
    ok = client.post("/api/settings", json={"ghost_pin": "99999", "current_ghost_pin": "12345"})
    assert ok.status_code == 200
    with dual["main"]() as s:
        assert pin_mod.verify_pin(s.query(GlobalSetting).first().ghost_pin, "99999")


def test_scrape_has_no_public_workspace_param(dual):
    schema = app.openapi()["paths"]["/api/scrape"]["post"]
    assert "parameters" not in schema or all(p["name"] != "workspace" for p in schema["parameters"])
