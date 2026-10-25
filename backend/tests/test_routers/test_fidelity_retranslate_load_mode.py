import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from database import get_db, Thread, Chapter, GlobalSetting
from services.background_translator import BackgroundTranslator


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _thread_with_chapter(db_session, load_mode: str):
    gs = db_session.execute(select(GlobalSetting)).scalar_one()
    gs.prefetch_mode = load_mode
    thread = Thread(title="Novel")
    db_session.add(thread)
    db_session.commit()
    chapter = Chapter(thread_id=thread.id, order=1, title_original="c", content_original="text", fidelity_warning="cut off")
    db_session.add(chapter)
    db_session.commit()
    return thread.id, chapter.id


@pytest.mark.parametrize("mode", ["hard", "soft"])
def test_batch_fidelity_retranslate_uses_the_global_load_mode(client, db_session, mode):
    thread_id, chapter_id = _thread_with_chapter(db_session, mode)

    with patch.object(BackgroundTranslator, "start_batch", new_callable=AsyncMock) as start_batch:
        response = client.post(f"/api/threads/{thread_id}/fidelity/retranslate", json={"chapter_ids": [chapter_id]})

    assert response.status_code == 200
    assert start_batch.call_args.kwargs["load_mode"] == mode


@pytest.mark.parametrize("mode", ["hard", "soft"])
def test_single_fidelity_retranslate_uses_the_global_load_mode(client, db_session, mode):
    thread_id, chapter_id = _thread_with_chapter(db_session, mode)

    with patch.object(BackgroundTranslator, "start_batch", new_callable=AsyncMock) as start_batch:
        response = client.post(f"/api/threads/{thread_id}/chapters/{chapter_id}/retranslate-fidelity")

    assert response.status_code == 200
    assert start_batch.call_args.kwargs["load_mode"] == mode
