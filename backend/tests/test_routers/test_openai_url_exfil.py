"""A-03: openai_url tidak boleh dipakai untuk mengalihkan API key ke host penyerang."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, GlobalSetting, get_db
from main import app
from services.ai.settings import resolve_active_base_url, upstream_error_message


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with Session() as s:
        s.add(
            GlobalSetting(
                llm_provider="openai",
                openai_url="https://api.openai.com/v1",
                openai_api_keys='["sk-real-key-1234567890"]',
            )
        )
        s.commit()

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    secrets = {"openai_api_key": "sk-real-openai-secret"}
    saved: dict = {}
    monkeypatch.setattr("routers.settings.load_secrets", lambda: secrets)
    monkeypatch.setattr(
        "routers.settings.save_secrets",
        lambda **kw: saved.update({k: v for k, v in kw.items() if v is not None}),
    )
    yield {"Session": Session, "saved": saved}
    app.dependency_overrides.clear()


def _stored(Session) -> GlobalSetting:
    with Session() as s:
        return s.execute(select(GlobalSetting)).scalar_one()


def test_changing_openai_host_clears_stored_keys(env):
    resp = TestClient(app).post("/api/settings", json={"openai_url": "https://attacker.example/v1"})
    assert resp.status_code == 200
    assert env["saved"].get("openai_api_key") == ""
    assert json.loads(_stored(env["Session"]).openai_api_keys) == []


def test_new_key_in_same_request_is_kept(env):
    TestClient(app).post(
        "/api/settings",
        json={"openai_url": "https://proxy.example/v1", "openai_api_key": "sk-new-for-proxy"},
    )
    assert env["saved"]["openai_api_key"] == "sk-new-for-proxy"


def test_same_host_keeps_keys(env):
    TestClient(app).post("/api/settings", json={"openai_url": "https://api.openai.com/v1/"})
    assert "openai_api_key" not in env["saved"]
    assert json.loads(_stored(env["Session"]).openai_api_keys) == ["sk-real-key-1234567890"]


@pytest.mark.parametrize("bad", ["file:///etc/passwd", "ftp://x.example", "javascript:alert(1)", "not a url"])
def test_non_http_openai_url_is_rejected(env, bad):
    resp = TestClient(app).post("/api/settings", json={"openai_url": bad})
    assert resp.status_code == 400


def test_request_lm_url_is_ignored_for_local_provider():
    class GS:
        llm_provider = "lm_studio"
        lm_url = "http://localhost:1234"

    assert resolve_active_base_url(GS(), "http://169.254.169.254/") == "http://localhost:1234"


def test_upstream_error_message_hides_body():
    msg = upstream_error_message(500, "SECRET-INTERNAL-PAGE")
    assert "500" in msg and "SECRET" not in msg
