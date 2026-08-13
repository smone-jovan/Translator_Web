import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Thread, Chapter

@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_export_epub_with_thoughts_and_images(client, db_session):
    # 1. Create a thread and chapter with thoughts and image tags
    test_thread = Thread(title="Export Test Novel", source_type="syosetu", source_url="http://test.org/novel")
    db_session.add(test_thread)
    db_session.commit()
    db_session.refresh(test_thread)

    content = """
    <think>
    Thinking process should be removed...
    </think>
    Ini adalah paragraf cerita pertama.
    <img src="/images/thread_1/test_illustration.png" alt="Illustration" />
    Ini adalah paragraf kedua.
    """
    ch = Chapter(
        thread_id=test_thread.id,
        title_original="Ch 1 Raw",
        title_translated="Bab 1 Terjemahan",
        content_original="Raw content",
        content_translated=content,
        order=0
    )
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    # 2. Test EPUB export with hide_thoughts=True
    res = client.post(
        f"/api/threads/{test_thread.id}/export",
        json={
            "format": "epub",
            "title": "Exported Test Novel",
            "author": "Tester",
            "chapter_ids": [ch.id],
            "hide_thoughts": True
        }
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/epub+zip"
    assert len(res.content) > 0

def test_export_txt(client, db_session):
    test_thread = Thread(title="Export TXT Novel", source_type="syosetu", source_url="http://test.org/novel2")
    db_session.add(test_thread)
    db_session.commit()
    db_session.refresh(test_thread)

    ch = Chapter(
        thread_id=test_thread.id,
        title_original="Ch 1 Raw",
        title_translated="Bab 1",
        content_translated="Teks terjemahan.",
        order=0
    )
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    res = client.post(
        f"/api/threads/{test_thread.id}/export",
        json={
            "format": "txt",
            "title": "Exported TXT Novel",
            "author": "Tester",
            "chapter_ids": [ch.id],
            "hide_thoughts": False
        }
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert b"Teks terjemahan." in res.content
