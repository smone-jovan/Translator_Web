import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, GlobalSetting, get_db
from main import app
from services.ai.secrets import mask_secret, is_masked_secret


@pytest.fixture
def mock_db_session(monkeypatch):
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Initialize a GlobalSetting with a real secret
    with TestingSessionLocal() as session:
        gs = GlobalSetting(
            ghost_pin="98765",
            openai_api_keys='["sk-real-key-1234567890"]',
        )
        session.add(gs)
        session.commit()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    fake_secrets = {
        "openai_api_key": "sk-real-openai-secret-key-1234",
        "gemini_api_key": "AIzaSyFakeGeminiKey5678",
        "openrouter_api_key": "sk-or-v1-fake-openrouter-key-9999",
    }
    monkeypatch.setattr("routers.settings.load_secrets", lambda: fake_secrets)
    saved = {}

    def mock_save_secrets(**kwargs):
        saved.update({k: v for k, v in kwargs.items() if v is not None})

    monkeypatch.setattr("routers.settings.save_secrets", mock_save_secrets)

    yield {"saved": saved, "Session": TestingSessionLocal, "secrets": fake_secrets}

    app.dependency_overrides.clear()


def test_mask_secret_helper():
    """Verify mask_secret helper masks properly and is_masked_secret detects it."""
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    masked = mask_secret("sk-1234567890abcdef")
    assert is_masked_secret(masked) is True
    assert "sk-" in masked
    assert "cdef" in masked
    assert "1234567890" not in masked
    assert is_masked_secret("sk-real-unmasked-key") is False


def test_get_settings_masks_secrets(mock_db_session):
    """GET /api/settings should return masked secrets, never plaintext."""
    client = TestClient(app)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()

    # Verify secrets are masked
    assert data["openai_api_key"] != "sk-real-openai-secret-key-1234"
    assert is_masked_secret(data["openai_api_key"])
    assert data["gemini_api_key"] != "AIzaSyFakeGeminiKey5678"
    assert is_masked_secret(data["gemini_api_key"])
    assert data["openrouter_api_key"] != "sk-or-v1-fake-openrouter-key-9999"
    assert is_masked_secret(data["openrouter_api_key"])
    assert data["ghost_pin"] != "98765"
    assert is_masked_secret(data["ghost_pin"])


def test_post_settings_preserves_masked_secrets(mock_db_session):
    """Submitting masked placeholder secrets in POST /api/settings should NOT overwrite real secrets."""
    client = TestClient(app)

    # 1. First get the masked values
    get_resp = client.get("/api/settings")
    masked_data = get_resp.json()

    # 2. Post them back along with a setting change
    post_payload = {
        "target_language": "English",
        "openai_api_key": masked_data["openai_api_key"],
        "gemini_api_key": masked_data["gemini_api_key"],
        "ghost_pin": masked_data["ghost_pin"],
    }
    post_resp = client.post("/api/settings", json=post_payload)
    assert post_resp.status_code == 200

    # Verify saved_secrets was NOT called with masked values
    saved = mock_db_session["saved"]
    assert "openai_api_key" not in saved
    assert "gemini_api_key" not in saved

    # Verify ghost_pin was not overwritten with the mask
    with mock_db_session["Session"]() as db:
        gs = db.query(GlobalSetting).first()
        assert gs.ghost_pin == "98765"
        assert gs.target_language == "English"
