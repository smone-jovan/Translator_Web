"""
Tests for Library Reading Status, Bookmark Timestamps, and Sorting APIs.
Verifies last_read_at mapping in ThreadItemOut and ThreadDetail.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Thread, Chapter, UserBookmark
from main import app
from routers.threads import get_db

# Isolated test database in memory
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_list_threads_returns_last_read_at_when_bookmarked(client):
    """Verify GET /api/threads includes last_read_at from UserBookmark."""
    db = TestingSessionLocal()
    
    # Create thread and chapters
    thread = Thread(title="Martial Peak", source_type="epub")
    db.add(thread)
    db.commit()
    db.refresh(thread)

    ch1 = Chapter(thread_id=thread.id, order=0, title_original="Chapter 1", title_translated="Bab 1")
    ch2 = Chapter(thread_id=thread.id, order=1, title_original="Chapter 2", title_translated="Bab 2")
    db.add_all([ch1, ch2])
    db.commit()
    db.refresh(ch2)
    ch2_id = ch2.id

    # Create bookmark with explicit last_read_at
    bookmark_time = datetime(2026, 8, 27, 6, 0, 0, tzinfo=timezone.utc)
    bookmark = UserBookmark(
        thread_id=thread.id,
        chapter_id=ch2_id,
        scroll_progress=50.0,
        last_read_at=bookmark_time
    )
    db.add(bookmark)
    db.commit()
    db.close()

    res = client.get("/api/threads")
    assert res.status_code == 200
    threads_data = res.json()
    assert len(threads_data) == 1
    
    item = threads_data[0]
    assert item["title"] == "Martial Peak"
    assert item["last_read"] == "Bab 2"
    assert item["last_read_id"] == ch2_id
    assert item["last_read_at"] is not None
    assert "2026-08-27" in item["last_read_at"]
    assert item["progress"] == 100  # (order 1 + 1) / 2 = 100%


def test_list_threads_returns_none_last_read_at_when_unread(client):
    """Verify unread threads have last_read_at=None and progress=0."""
    db = TestingSessionLocal()
    thread = Thread(title="Renegade Immortal", source_type="url")
    db.add(thread)
    db.commit()
    db.refresh(thread)

    ch1 = Chapter(thread_id=thread.id, order=0, title_original="Ch 1", title_translated="Bab 1")
    db.add(ch1)
    db.commit()
    db.close()

    res = client.get("/api/threads")
    assert res.status_code == 200
    threads_data = res.json()
    assert len(threads_data) == 1
    
    item = threads_data[0]
    assert item["title"] == "Renegade Immortal"
    assert item["last_read"] is None
    assert item["last_read_id"] is None
    assert item["last_read_at"] is None
    assert item["progress"] == 0


def test_get_thread_detail_includes_last_read_at(client):
    """Verify GET /api/threads/{thread_id} includes last_read_at."""
    db = TestingSessionLocal()
    thread = Thread(title="Lord of the Mysteries", source_type="epub")
    db.add(thread)
    db.commit()
    db.refresh(thread)
    thread_id = thread.id

    ch1 = Chapter(thread_id=thread_id, order=0, title_original="Ch 1", title_translated="Bab 1")
    db.add(ch1)
    db.commit()
    db.refresh(ch1)
    ch1_id = ch1.id

    bookmark = UserBookmark(
        thread_id=thread_id,
        chapter_id=ch1_id,
        scroll_progress=10.0,
        last_read_at=datetime(2026, 8, 27, 5, 30, 0)
    )
    db.add(bookmark)
    db.commit()
    db.close()

    res = client.get(f"/api/threads/{thread_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Lord of the Mysteries"
    assert data["last_read_id"] == ch1_id
    assert data["last_read_at"] is not None
    assert "2026-08-27" in data["last_read_at"]
