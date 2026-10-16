"""
ADR-122 regression: terms just created by the user must never be the first ones archived when
the glossary is at its max_context_terms limit (the "self-eviction paradox"). The single and
/bulk create routes already protect them; the bulk-action "import" and unlocked genre-preset
paths used the ORM default usage_count=0 and were evicted first.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import LorebookEntry, Thread, get_db
from main import app


@pytest.fixture
def client(db_session, default_global_settings):
    default_global_settings.max_context_terms = 3
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def full_thread(db_session):
    """A thread whose active glossary is exactly at the limit (3) with older, used terms."""
    t = Thread(title="Glossary", source_type="txt")
    db_session.add(t)
    db_session.commit()
    old = datetime.utcnow() - timedelta(days=30)
    for i in range(3):
        db_session.add(LorebookEntry(
            thread_id=t.id, original_term=f"旧{i}", translated_term=f"Old{i}",
            usage_count=1, last_used_at=old, created_at=old,
        ))
    db_session.commit()
    return t


def _active_terms(db_session, thread_id):
    db_session.expire_all()
    rows = db_session.execute(
        select(LorebookEntry).where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)  # noqa: E712
    ).scalars().all()
    return {r.original_term for r in rows}


def test_bulk_import_new_terms_not_self_evicted_at_limit(client, db_session, full_thread):
    res = client.post(
        f"/api/threads/{full_thread.id}/lorebook/action",
        json={"action": "import", "entries": [{"original_term": "新词", "translated_term": "NewTerm"}]},
    )
    assert res.status_code == 200, res.text
    active = _active_terms(db_session, full_thread.id)
    assert "新词" in active
    assert len(active) == 3


def test_apply_preset_unlocked_terms_not_self_evicted_at_limit(client, db_session, full_thread):
    res = client.post(
        f"/api/threads/{full_thread.id}/presets/xianxia",
        json={"lock_entries": False, "target_language": "Indonesian"},
    )
    assert res.status_code == 200, res.text
    added = res.json()["added"]
    assert added > 0
    active = _active_terms(db_session, full_thread.id)
    old_terms = {f"旧{i}" for i in range(3)}
    # The limit is 3, so the freshly applied preset terms must win over the 30-day-old ones
    assert not (active & old_terms), active
    assert len(active) == 3
