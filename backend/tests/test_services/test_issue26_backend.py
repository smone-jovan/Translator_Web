"""Regression tests for issue #26 backend items (A-12, A-13, A-14, A-16)."""
import asyncio
import datetime
import json
from unittest.mock import patch

import pytest
from sqlalchemy import select

import database
from database import Chapter, GlobalSetting, Thread, get_session, make_workspace_key
from services import background_translator as bt
from services.background_translator import BackgroundTranslator, active_tasks, translation_queues


# ---------------------------------------------------------------- A-12
@pytest.mark.asyncio
async def test_do_translate_resolves_provider_with_workspace_session(monkeypatch):
    """Provider must come from the job's own workspace DB, never the process-global ACTIVE_WORKSPACE."""
    monkeypatch.setattr(database, "ACTIVE_WORKSPACE", "main")
    with get_session("ghost") as db:
        thread = Thread(title="T")
        db.add(thread)
        db.flush()
        chapter = Chapter(thread_id=thread.id, order=1, content_original="hello " * 20)
        db.add(chapter)
        db.commit()
        thread_id, chapter_id = thread.id, chapter.id

    seen = {}

    def fake_get_provider(**kwargs):
        sess = kwargs.get("db_session")
        seen["workspace"] = getattr(sess, "_workspace", None)
        raise RuntimeError("stop here")

    monkeypatch.setattr(bt.AIProviderFactory, "get_provider", staticmethod(fake_get_provider))
    await BackgroundTranslator._do_translate(
        chapter_id, thread_id, "Indonesian", model="m", lm_url="http://localhost:1234", workspace="ghost"
    )
    assert seen.get("workspace") == "ghost"


# ---------------------------------------------------------------- A-13
@pytest.mark.asyncio
async def test_duplicate_request_does_not_send_done_to_other_listeners():
    key = make_workspace_key("main", 9001)
    q = asyncio.Queue()
    translation_queues[key] = [q]
    active_tasks[key] = asyncio.create_task(asyncio.sleep(5))
    try:
        result = await BackgroundTranslator.run_chapter_translation(
            chapter_id=9001, thread_id=1, target_lang="Indonesian", workspace="main"
        )
        assert result is False
        assert q.empty(), "duplicate request must not terminate the owner's stream"
    finally:
        active_tasks.pop(key).cancel()
        translation_queues.pop(key, None)


@pytest.mark.asyncio
async def test_stream_queue_registered_before_job_is_spawned(db_session):
    from routers import translate as tr

    db_session._workspace = "main"
    key = make_workspace_key("main", 9002)
    observed = {}

    def fake_spawn(coro):
        observed["queues"] = list(translation_queues.get(key, []))
        coro.close()

    req = tr.TranslateRequest(text="x", thread_id=1, chapter_id=9002, lm_url="http://localhost:1234", model="m")
    with patch.object(tr, "spawn_background_task", fake_spawn):
        resp = await tr.translate_stream(req, db_session)
    try:
        assert len(observed["queues"]) == 1
    finally:
        translation_queues.pop(key, None)
        await resp.body_iterator.aclose()


# ---------------------------------------------------------------- A-14
@pytest.mark.asyncio
async def test_batch_chapter_is_registered_in_active_tasks(monkeypatch):
    key = make_workspace_key("main", 9003)
    seen = {}

    async def fake_do_translate(chapter_id, **kwargs):
        seen["registered"] = key in active_tasks
        return True

    monkeypatch.setattr(BackgroundTranslator, "_do_translate", staticmethod(fake_do_translate))
    ok = await BackgroundTranslator._translate_registered("main", 9003)
    assert ok is True
    assert seen["registered"] is True
    assert key not in active_tasks


# ---------------------------------------------------------------- A-16
@pytest.mark.asyncio
async def test_pacing_rotation_persists_for_detached_settings(db_session):
    gs = GlobalSetting(
        llm_provider="gemini",
        gemini_api_keys=json.dumps(["keyA", "keyB", "keyC"]),
        gemini_active_key_index=0,
    )
    db_session.add(gs)
    db_session.commit()
    db_session.refresh(gs)
    db_session.expunge(gs)  # settings loaded by a session that has since closed

    await BackgroundTranslator._enforce_pacing("gemini-3.5-flash-lite", gs, db_session=db_session)

    stored = db_session.execute(select(GlobalSetting)).scalar_one()
    db_session.refresh(stored)
    assert stored.gemini_active_key_index == 1


def test_gemini_key_choice_uses_full_list_index_and_skips_exhausted(monkeypatch):
    from services.ai import secrets

    gs = GlobalSetting(
        llm_provider="gemini",
        gemini_model="",
        gemini_api_keys=json.dumps(["keyA", "keyB", "keyC"]),
        gemini_active_key_index=2,
    )
    monkeypatch.setattr(secrets, "exhausted_gemini_keys", {"keyA": datetime.date.today().isoformat()})
    assert secrets.get_active_api_key("gemini", gs) == "keyC"
