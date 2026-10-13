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


def test_export_epub_bundles_remote_images(client, db_session, monkeypatch):
    import zipfile
    import io
    import httpx

    test_thread = Thread(title="Remote Image Test", source_type="novalpie")
    db_session.add(test_thread)
    db_session.commit()
    db_session.refresh(test_thread)

    fake_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    # Mock httpx GET requests
    async def mock_async_get(self, url, *args, **kwargs):
        return httpx.Response(200, content=fake_png, headers={"content-type": "image/png"})

    def mock_sync_get(self, url, *args, **kwargs):
        return httpx.Response(200, content=fake_png, headers={"content-type": "image/png"})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_async_get)
    monkeypatch.setattr(httpx.Client, "get", mock_sync_get)

    content = """
    Paragraf satu cerita.
    ![Ilustrasi Ajaib](https://images.novelpia.com/imagebox/cover/test_remote_image.file)
    Paragraf dua cerita.
    """
    ch = Chapter(
        thread_id=test_thread.id,
        title_original="Ch 1",
        title_translated="Bab 1",
        content_translated=content,
        order=0
    )
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    res = client.post(
        f"/api/threads/{test_thread.id}/export",
        json={
            "format": "epub",
            "title": "Remote Image Book",
            "author": "Tester",
            "chapter_ids": [ch.id],
            "hide_thoughts": False
        }
    )
    assert res.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    namelist = zf.namelist()

    # Must contain at least one bundled image in EPUB/images/
    img_files = [f for f in namelist if f.startswith("EPUB/images/")]
    assert len(img_files) >= 1, f"Expected bundled image in EPUB, found namelist: {namelist}"

    # Verify chapter_1.xhtml references the bundled image path and not the external URL
    ch_html = zf.read("EPUB/chapter_1.xhtml").decode("utf-8")
    assert "https://images.novelpia.com" not in ch_html
    assert "images/" in ch_html


def test_export_enforces_glossary_locking(client, db_session):
    from database import LorebookEntry
    test_thread = Thread(title="Glossary Export Test", source_type="syosetu")
    db_session.add(test_thread)
    db_session.commit()
    db_session.refresh(test_thread)

    # Add a glossary rule: "罗毅 / Luo Yi" -> "Rahmat"
    entry = LorebookEntry(
        thread_id=test_thread.id,
        original_term="罗毅 / Luo Yi",
        translated_term="Rahmat",
        notes="Protagonist"
    )
    db_session.add(entry)

    # Chapter has un-locked / mistranslated text in DB: "Luo Yi berjalan bersama Luo Yi."
    ch = Chapter(
        thread_id=test_thread.id,
        title_original="Ch 1",
        title_translated="Petualangan Luo Yi",
        content_translated="Luo Yi pergi ke pasar dan membeli pedang.",
        order=0
    )
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    # Export to TXT
    res = client.post(
        f"/api/threads/{test_thread.id}/export",
        json={
            "format": "txt",
            "title": "Buku Uji",
            "author": "SMONE",
            "chapter_ids": [ch.id],
            "hide_thoughts": False
        }
    )
    assert res.status_code == 200
    txt_content = res.content.decode("utf-8")
    assert "Petualangan Rahmat" in txt_content
    assert "Rahmat pergi ke pasar dan membeli pedang." in txt_content
    assert "Luo Yi" not in txt_content

    # Export to EPUB
    res_epub = client.post(
        f"/api/threads/{test_thread.id}/export",
        json={
            "format": "epub",
            "title": "Buku Uji EPUB",
            "author": "SMONE",
            "chapter_ids": [ch.id],
            "hide_thoughts": False
        }
    )
    assert res_epub.status_code == 200
    import zipfile
    import io
    zf = zipfile.ZipFile(io.BytesIO(res_epub.content))
    ch_html = zf.read("EPUB/chapter_1.xhtml").decode("utf-8")
    assert "Petualangan Rahmat" in ch_html
    assert "Rahmat pergi ke pasar dan membeli pedang." in ch_html
    assert "Luo Yi" not in ch_html


