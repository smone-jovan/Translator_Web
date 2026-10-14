import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Thread, Chapter, GlobalSetting
from services.ai.settings import resolve_active_model
from routers.threads import (
    delete_all_translations,
    fix_truncated_translations,
    get_thread_fidelity_issues,
)


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    t = Thread(id=1, original_title="Audit Novel", title="Audit Novel")
    session.add(t)

    # Ch 1: done with fidelity warning (ends with full sentence)
    ch1 = Chapter(
        id=101,
        thread_id=1,
        order=1,
        title_original="Ch 1",
        title_translated="Bab 1",
        content_original="Original text 1.",
        content_translated="Translated text 1.",
        translation_status="done",
        fidelity_warning="Paragraph ratio mismatch",
    )
    # Ch 2: truncated mid-sentence with fidelity warning
    ch2 = Chapter(
        id=102,
        thread_id=1,
        order=2,
        title_original="Ch 2",
        title_translated="Bab 2",
        content_original="Original text 2",
        content_translated="The hero was running through the forest and then he saw a",  # truncated
        translation_status="done",
        fidelity_warning="Truncated mid-sentence",
    )
    # Ch 3: clean untranslated
    ch3 = Chapter(
        id=103,
        thread_id=1,
        order=3,
        title_original="Ch 3",
        title_translated=None,
        content_original="Original text 3",
        content_translated=None,
        translation_status="idle",
        fidelity_warning=None,
    )
    session.add_all([ch1, ch2, ch3])
    session.commit()

    yield session
    session.close()


def test_resolve_active_model_guards_all_cloud_providers():
    class DummySettings:
        llm_provider = "gemini"
        gemini_model = "gemini-2.5-flash"
        openai_model = "gpt-4o-mini"
        openrouter_model = "deepseek/deepseek-chat"
        lm_model = "qwen2.5-7b-instruct-gemma-like"

    gs = DummySettings()

    # Gemini: local lm_model containing 'gemma' or 'gemini' must NOT override cloud model
    assert resolve_active_model(gs, requested_model="qwen2.5-7b-instruct-gemma-like") == "gemini-2.5-flash"
    assert resolve_active_model(gs, requested_model="gemini-2.5-pro") == "gemini-2.5-pro"
    assert resolve_active_model(gs, requested_model=None) == "gemini-2.5-flash"

    # OpenAI: local lm_model containing 'gpt' must NOT override cloud model
    gs.llm_provider = "openai"
    gs.lm_model = "local-gpt-oss"
    assert resolve_active_model(gs, requested_model="local-gpt-oss") == "gpt-4o-mini"
    assert resolve_active_model(gs, requested_model="gpt-4o") == "gpt-4o"
    assert resolve_active_model(gs, requested_model=None) == "gpt-4o-mini"

    # OpenRouter: local lm_model without slash must NOT override
    gs.llm_provider = "openrouter"
    assert resolve_active_model(gs, requested_model="local-gpt-oss") == "deepseek/deepseek-chat"
    assert resolve_active_model(gs, requested_model="anthropic/claude-3.5-haiku") == "anthropic/claude-3.5-haiku"


def test_get_thread_fidelity_issues_filters_and_counts(test_db):
    res = get_thread_fidelity_issues(thread_id=1, db=test_db)
    assert res.total_chapters == 3
    assert res.flagged_chapters_count == 2
    assert len(res.issues) == 2
    assert {i.chapter_id for i in res.issues} == {101, 102}


def test_fix_truncated_translations_resets_fidelity_warning(test_db):
    res = fix_truncated_translations(thread_id=1, db=test_db)
    assert res["reset_count"] == 1

    ch2 = test_db.query(Chapter).filter_by(id=102).first()
    assert ch2.translation_status == "idle"
    assert ch2.content_translated is None
    assert ch2.fidelity_warning is None


def test_delete_all_translations_clears_fidelity_warning(test_db):
    res = asyncio.run(delete_all_translations(thread_id=1, db=test_db))
    assert res["status"] == "ok"

    chapters = test_db.query(Chapter).filter_by(thread_id=1).all()
    for ch in chapters:
        assert ch.content_translated is None
        assert ch.translation_status == "idle"
        assert ch.fidelity_warning is None
