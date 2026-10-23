"""Issue 25: a finished translation must survive non-fatal side failures (A-06), and a fetch-only
pass must not demote a translated chapter back to idle (A-11)."""
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.background_translator as bt
from database import Base, Chapter, GlobalSetting, Thread

TRANSLATION = "Yun Yi bertemu Lin Yue di depan gerbang gunung."


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with Factory() as db:
        db.add(GlobalSetting(llm_provider="lm_studio"))
        thread = Thread(title="T")
        db.add(thread)
        db.flush()
        db.add(Chapter(id=1, thread_id=thread.id, order=1, content_original="云逸在山门前遇见了林月。"))
        db.commit()
        thread_id = thread.id

    @contextmanager
    def fake_get_session(workspace="main"):
        db = Factory()
        db._workspace = workspace
        try:
            yield db
        finally:
            db.close()

    async def no_pacing(*args, **kwargs):
        return None

    monkeypatch.setattr(bt, "get_session", fake_get_session)
    monkeypatch.setattr(bt.BackgroundTranslator, "_enforce_pacing", staticmethod(no_pacing))
    return {"thread_id": thread_id, "factory": Factory}


class _FixedProvider:
    async def stream_chat(self, messages, **kwargs):
        yield TRANSLATION


@pytest.mark.asyncio
async def test_glossary_autosave_failure_keeps_the_finished_translation(env, monkeypatch):
    monkeypatch.setattr(bt.AIProviderFactory, "get_provider", staticmethod(lambda **kw: _FixedProvider()))

    def failing_autosave(*args, **kwargs):
        raise RuntimeError("glossary store unavailable")

    monkeypatch.setattr(bt.ContextEngine, "auto_save_glossary", staticmethod(failing_autosave))

    ok = await bt.BackgroundTranslator._do_translate(
        chapter_id=1, thread_id=env["thread_id"], target_lang="Indonesian",
        load_mode="hard", workspace="main",
    )

    assert ok is True
    with env["factory"]() as db:
        chapter = db.get(Chapter, 1)
        assert chapter.translation_status == "done"
        assert TRANSLATION in (chapter.content_translated or "")


@pytest.mark.asyncio
async def test_fetch_only_keeps_a_translated_chapter_done(env):
    with env["factory"]() as db:
        chapter = db.get(Chapter, 1)
        chapter.content_translated = "Terjemahan yang sudah diedit manual."
        chapter.translation_status = "done"
        db.commit()

    ok = await bt.BackgroundTranslator._do_translate(
        chapter_id=1, thread_id=env["thread_id"], target_lang="Indonesian",
        fetch_only=True, workspace="main",
    )

    assert ok is True
    with env["factory"]() as db:
        chapter = db.get(Chapter, 1)
        assert chapter.translation_status == "done"
        assert chapter.content_translated == "Terjemahan yang sudah diedit manual."


@pytest.mark.asyncio
async def test_fetch_only_still_resets_a_failed_chapter_to_idle(env):
    with env["factory"]() as db:
        db.get(Chapter, 1).translation_status = "error"
        db.commit()

    await bt.BackgroundTranslator._do_translate(
        chapter_id=1, thread_id=env["thread_id"], target_lang="Indonesian",
        fetch_only=True, workspace="main",
    )

    with env["factory"]() as db:
        assert db.get(Chapter, 1).translation_status == "idle"
