"""
ADR-123: the glossary limit has one default (150) everywhere. ContextEngine used to fall back to
50 when GlobalSetting was missing and crashed (None comparison) when max_context_terms was NULL.
"""
from sqlalchemy import select

from database import GlobalSetting, LorebookEntry, Thread
from services.context_engine import ContextEngine


def _thread_with_terms(db_session, n):
    t = Thread(title="Limit", source_type="txt")
    db_session.add(t)
    db_session.commit()
    db_session.add_all([
        LorebookEntry(thread_id=t.id, original_term=f"词{i}", translated_term=f"T{i}", usage_count=1)
        for i in range(n)
    ])
    db_session.commit()
    return t


def _active_count(db_session, thread_id):
    db_session.expire_all()
    return len(db_session.execute(
        select(LorebookEntry).where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)  # noqa: E712
    ).scalars().all())


def test_context_engine_limit_fallback_is_150_without_global_settings(db_session):
    t = _thread_with_terms(db_session, 100)
    ContextEngine.enforce_context_limit(db_session, t.id)
    assert _active_count(db_session, t.id) == 100


def test_context_engine_limit_fallback_is_150_when_setting_is_null(db_session):
    db_session.add(GlobalSetting(max_context_terms=None))
    db_session.commit()
    t = _thread_with_terms(db_session, 160)
    ContextEngine.enforce_context_limit(db_session, t.id)
    assert _active_count(db_session, t.id) == 150
