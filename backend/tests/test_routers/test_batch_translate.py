import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from database import get_db, Thread, GlobalSetting
from services.background_translator import BackgroundTranslator

@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_batch_translate_passes_load_mode_to_background_translator(client, db_session):
    # Arrange: create a thread in DB
    thread = Thread(title="Test Novel")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    with patch.object(BackgroundTranslator, "start_batch", new_callable=AsyncMock) as mock_start_batch:
        # Act: call batch-translate with load_mode="hard"
        response = client.post(
            f"/api/threads/{thread.id}/batch-translate",
            json={
                "chapter_ids": [1, 2],
                "ai_extract": True,
                "target_lang": "Indonesian",
                "overwrite": True,
                "translation_mode": "quality",
                "load_mode": "hard"
            }
        )

        # Assert
        assert response.status_code == 200
        assert mock_start_batch.called
        kwargs = mock_start_batch.call_args.kwargs
        assert kwargs.get("load_mode") == "hard"

def test_batch_translate_defaults_load_mode_to_global_setting(client, db_session):
    # Arrange: set prefetch_mode to "hard" in global settings
    gs = db_session.execute(select(GlobalSetting)).scalar_one_or_none()
    if not gs:
        gs = GlobalSetting(prefetch_mode="hard")
        db_session.add(gs)
    else:
        gs.prefetch_mode = "hard"
    db_session.commit()

    thread = Thread(title="Test Novel 2")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    with patch.object(BackgroundTranslator, "start_batch", new_callable=AsyncMock) as mock_start_batch:
        # Act: call without load_mode
        response = client.post(
            f"/api/threads/{thread.id}/batch-translate",
            json={
                "chapter_ids": [1, 2],
                "ai_extract": True,
                "target_lang": "Indonesian",
                "overwrite": True,
                "translation_mode": "quality"
            }
        )

        # Assert
        assert response.status_code == 200
        assert mock_start_batch.called
        kwargs = mock_start_batch.call_args.kwargs
        assert kwargs.get("load_mode") == "hard"


def test_translate_endpoint_saves_fidelity_warning(client, db_session):
    from database import Chapter
    from services.ai.base import BaseAIProviderAdapter

    class MockProvider(BaseAIProviderAdapter):
        async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
            # Return truncated translation without proper sentence-ending punctuation
            return "Hasil terjemahan yang terpotong di tengah kalimat dan tiba-tiba dia melihat"

        async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
            yield "Hasil terjemahan yang terpotong di tengah kalimat dan tiba-tiba dia melihat"

    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=MockProvider()):
        resp = client.post(
            "/api/translate",
            json={
                "text": "Bab 1: Pertarungan di Puncak Gunung.\n\nLin En melangkah maju menghadapi musuh bebuyutannya dengan gagah berani.",
                "target_lang": "Indonesian"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] is not None

        chapter = db_session.get(Chapter, data["chapter_id"])
        assert chapter is not None
        assert chapter.fidelity_warning is not None
        assert "cut off mid-sentence" in chapter.fidelity_warning



def test_batch_translate_uses_global_load_mode_when_prefetch_disabled(client, db_session):
    # Arrange: prefetch is DISABLED (0), but global load_mode / prefetch_mode is "hard"
    gs = db_session.execute(select(GlobalSetting)).scalar_one_or_none()
    if not gs:
        gs = GlobalSetting(prefetch_enabled=0, prefetch_mode="hard")
        db_session.add(gs)
    else:
        gs.prefetch_enabled = 0
        gs.prefetch_mode = "hard"
    db_session.commit()

    thread = Thread(title="Test Novel Prefetch Disabled")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    with patch.object(BackgroundTranslator, "start_batch", new_callable=AsyncMock) as mock_start_batch:
        response = client.post(
            f"/api/threads/{thread.id}/batch-translate",
            json={
                "chapter_ids": [10, 11],
                "ai_extract": True,
                "target_lang": "Indonesian",
                "overwrite": True,
                "translation_mode": "quality"
            }
        )
        assert response.status_code == 200
        assert mock_start_batch.called
        assert mock_start_batch.call_args.kwargs.get("load_mode") == "hard"


def test_settings_can_update_load_mode_independently(client, db_session):
    # Verify /api/settings can set load_mode / prefetch_mode
    response = client.post(
        "/api/settings",
        json={"prefetch_mode": "hard"}
    )
    assert response.status_code == 200

    # Read back settings
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    assert get_res.json()["prefetch_mode"] == "hard"


def test_batch_translate_persists_load_mode_to_global_settings(client, db_session):
    thread = Thread(title="Test Novel Persist")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    with patch.object(BackgroundTranslator, "start_batch", new_callable=AsyncMock):
        response = client.post(
            f"/api/threads/{thread.id}/batch-translate",
            json={
                "chapter_ids": [1, 2],
                "ai_extract": True,
                "target_lang": "Indonesian",
                "overwrite": True,
                "translation_mode": "quality",
                "load_mode": "hard"
            }
        )
        assert response.status_code == 200

    # Verify GlobalSetting was updated in database
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    assert get_res.json()["prefetch_mode"] == "hard"
    assert get_res.json()["load_mode"] == "hard"

