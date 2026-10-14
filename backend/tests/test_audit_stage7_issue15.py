import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from database import Base, Thread, Chapter, UserBookmark, LorebookEntry, init_db
from routers.threads import list_threads, get_thread


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed thread with 5 chapters
    t = Thread(id=1, original_title="Novel Perf", title="Novel Perf")
    session.add(t)

    for i in range(5):
        ch = Chapter(
            id=200 + i,
            thread_id=1,
            order=i,
            title_original=f"Raw {i}",
            title_translated=f"Chapter {i}",
            content_original=f"Original content for chapter {i} " * 50,
            content_translated=f"Translated content for chapter {i} " * 50 if i < 3 else None,
            translation_status="done" if i < 3 else "idle",
        )
        session.add(ch)

    session.commit()
    yield session
    session.close()


def test_sqlite_indexes_created():
    # Verify indexes exist on Chapter and UserBookmark
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    chapter_cols = {col["name"]: col for col in inspector.get_columns("chapters")}
    assert "thread_id" in chapter_cols

    indexes = [idx["name"] for idx in inspector.get_indexes("chapters")]
    # Check that either direct column index or composite index exists
    has_thread_idx = any("thread_id" in idx or "order" in idx for idx in indexes)
    assert has_thread_idx


def test_list_threads_lightweight_query(test_db):
    threads = list_threads(db=test_db)
    assert len(threads) == 1
    t = threads[0]
    # Thread detail should report 5 chapters with 3 translated
    assert t.chapter_count == 5
    assert t.translations_count == 3


def test_get_thread_lightweight_metadata(test_db):
    res = get_thread(thread_id=1, db=test_db)
    assert res.id == 1
    assert len(res.chapters) == 5
    # First 3 chapters should have is_translated=True
    assert res.chapters[0].has_translation is True
    assert res.chapters[1].has_translation is True
    assert res.chapters[2].has_translation is True
    assert res.chapters[3].has_translation is False
    assert res.chapters[4].has_translation is False
