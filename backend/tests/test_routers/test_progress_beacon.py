import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Thread, Chapter, UserBookmark
from sqlalchemy import select

@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_progress_beacon_formats_and_deduplication(client, db_session):
    # 1. Create a test thread and chapters
    test_thread = Thread(title="Test Novel", source_type="syosetu", source_url="http://test.org/novel")
    db_session.add(test_thread)
    db_session.commit()
    db_session.refresh(test_thread)

    ch1 = Chapter(thread_id=test_thread.id, title_original="Ch 1", order=0)
    ch2 = Chapter(thread_id=test_thread.id, title_original="Ch 2", order=1)
    db_session.add_all([ch1, ch2])
    db_session.commit()
    db_session.refresh(ch1)
    db_session.refresh(ch2)

    # 2. Test standard application/json POST /progress
    res1 = client.post(
        f"/api/threads/{test_thread.id}/chapters/{ch1.id}/progress",
        json={"scroll_progress": 42.5}
    )
    assert res1.status_code == 200
    assert res1.json()["scroll_progress"] == 42.5

    # 3. Test sendBeacon text/plain POST /progress (browser sendBeacon default format)
    res2 = client.post(
        f"/api/threads/{test_thread.id}/chapters/{ch2.id}/progress",
        content='{"scroll_progress": 88.0}',
        headers={"Content-Type": "text/plain;charset=UTF-8"}
    )
    assert res2.status_code == 200
    assert res2.json()["scroll_progress"] == 88.0

    # 4. Verify in DB that only 1 UserBookmark exists and it points to ch2 with 88.0 scroll
    bookmarks = db_session.execute(
        select(UserBookmark).where(UserBookmark.thread_id == test_thread.id)
    ).scalars().all()
    assert len(bookmarks) == 1
    assert bookmarks[0].chapter_id == ch2.id
    assert bookmarks[0].scroll_progress == 88.0
