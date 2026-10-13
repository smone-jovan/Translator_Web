import pytest
import io
from fastapi.testclient import TestClient
from main import app
from database import get_db, Thread, Chapter
from routers.export import ExportRequest

@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_export_request_default_author_is_smone():
    """Verify ExportRequest defaults author to 'SMONE' if omitted."""
    req = ExportRequest(
        format="epub",
        title="Test Novel",
        chapter_ids=[1, 2]
    )
    assert req.author == "SMONE"

def test_export_epub_default_author_smone(client, db_session):
    """Verify exporting EPUB without specifying author defaults to 'SMONE'."""
    test_thread = Thread(title="Author Test Novel", source_type="epub", author="SMONE")
    db_session.add(test_thread)
    db_session.commit()
    db_session.refresh(test_thread)

    ch = Chapter(
        thread_id=test_thread.id,
        title_original="Ch 1",
        title_translated="Bab 1",
        content_original="Content",
        content_translated="Terjemahan",
        order=0
    )
    db_session.add(ch)
    db_session.commit()

    res = client.post(
        f"/api/threads/{test_thread.id}/export",
        json={
            "format": "epub",
            "title": "Author Test Novel",
            "chapter_ids": [ch.id]
        }
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/epub+zip"
