"""
GET /chapters/{id}?track=0 dipakai Pocket Offline Cache untuk mengunduh banyak bab sekaligus.
Mode ini harus bebas efek samping: tidak memindahkan bookmark/posisi baca dan tidak memicu prefetch.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import Chapter, Thread, UserBookmark, get_db
from main import app


@pytest.fixture
def client(db_session, default_global_settings):
    default_global_settings.prefetch_enabled = 1
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def thread_with_chapters(db_session):
    t = Thread(title="Peek", source_type="txt")
    db_session.add(t)
    db_session.commit()
    chs = [
        Chapter(thread_id=t.id, order=i, content_original=f"o{i}", content_translated=f"t{i}",
                translation_status="done")
        for i in range(3)
    ]
    db_session.add_all(chs)
    db_session.commit()
    db_session.add(UserBookmark(thread_id=t.id, chapter_id=chs[0].id, scroll_progress=37.5))
    db_session.commit()
    return t, chs


def _bookmark(db_session, thread_id):
    db_session.expire_all()
    return db_session.execute(select(UserBookmark).where(UserBookmark.thread_id == thread_id)).scalars().first()


def test_track_zero_keeps_bookmark_and_skips_prefetch(client, db_session, thread_with_chapters):
    t, chs = thread_with_chapters
    with patch("services.background_translator.BackgroundTranslator.check_and_prefetch") as prefetch, \
         patch("services.background_translator.BackgroundTranslator.run_chapter_translation") as translate:
        res = client.get(f"/api/threads/{t.id}/chapters/{chs[2].id}?track=0")

    assert res.status_code == 200
    assert res.json()["content_translated"] == "t2"
    bm = _bookmark(db_session, t.id)
    assert bm.chapter_id == chs[0].id
    assert bm.scroll_progress == 37.5
    prefetch.assert_not_called()
    translate.assert_not_called()


def test_default_get_still_tracks_reading_position(client, db_session, thread_with_chapters):
    t, chs = thread_with_chapters
    with patch("services.background_translator.BackgroundTranslator.check_and_prefetch") as prefetch:
        res = client.get(f"/api/threads/{t.id}/chapters/{chs[1].id}")

    assert res.status_code == 200
    bm = _bookmark(db_session, t.id)
    assert bm.chapter_id == chs[1].id
    assert bm.scroll_progress == 0.0
    prefetch.assert_called_once()


# --- Council follow-up: close mutants the tests above could not catch -----------------

def _make_thread(db_session, translated=True, bookmark=True):
    t = Thread(title="Peek2", source_type="txt")
    db_session.add(t)
    db_session.commit()
    chs = [
        Chapter(thread_id=t.id, order=i, content_original=f"o{i}",
                content_translated=(f"t{i}" if translated else None),
                translation_status=("done" if translated else "idle"))
        for i in range(3)
    ]
    db_session.add_all(chs)
    db_session.commit()
    if bookmark:
        db_session.add(UserBookmark(thread_id=t.id, chapter_id=chs[0].id, scroll_progress=37.5))
        db_session.commit()
    return t, chs


def test_track_zero_never_queues_translation_of_untranslated_chapter(client, db_session):
    t, chs = _make_thread(db_session, translated=False)
    with patch("services.background_translator.BackgroundTranslator.check_and_prefetch"), \
         patch("services.background_translator.BackgroundTranslator.run_chapter_translation") as translate:
        assert client.get(f"/api/threads/{t.id}/chapters/{chs[1].id}?track=0").status_code == 200
        translate.assert_not_called()
        # Control: a tracked read of the same chapter does queue it (proves the patch target is live)
        assert client.get(f"/api/threads/{t.id}/chapters/{chs[1].id}").status_code == 200
        translate.assert_called_once()


def test_track_zero_reports_saved_scroll_only_for_bookmarked_chapter(client, db_session):
    t, chs = _make_thread(db_session)
    with patch("services.background_translator.BackgroundTranslator.check_and_prefetch"):
        same = client.get(f"/api/threads/{t.id}/chapters/{chs[0].id}?track=0").json()
        other = client.get(f"/api/threads/{t.id}/chapters/{chs[2].id}?track=0").json()
    assert same["scroll_progress"] == 37.5
    assert other["scroll_progress"] == 0.0


def test_track_zero_does_not_create_a_bookmark(client, db_session):
    t, chs = _make_thread(db_session, bookmark=False)
    with patch("services.background_translator.BackgroundTranslator.check_and_prefetch"):
        assert client.get(f"/api/threads/{t.id}/chapters/{chs[1].id}?track=0").status_code == 200
    db_session.expire_all()
    assert db_session.execute(select(UserBookmark).where(UserBookmark.thread_id == t.id)).scalars().all() == []
