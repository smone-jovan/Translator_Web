import inspect
import io
import os
import re
import socket
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base, Thread, Chapter, GlobalSetting
from main import app


@pytest.fixture
def test_db_setup(monkeypatch):
    """Isolated in-memory database setup for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionTest() as db:
        gs = GlobalSetting(
            translation_mode="quality",
            display_mode="both",
            scraper_concurrency=2,
            novalpie_auth_enabled=0,
            novalpie_cookie="",
        )
        db.add(gs)
        t = Thread(title="Test Novel", original_title="Test Novel", source_type="manual")
        db.add(t)
        db.flush()

        ch = Chapter(
            thread_id=t.id,
            order=1,
            title_original="Chapter 1",
            content_original="",
            source_url="http://127.0.0.1:8000/internal-test",
        )
        db.add(ch)
        db.commit()

    monkeypatch.setattr("database.SessionLocalMain", SessionTest)
    monkeypatch.setattr("database.SessionLocalGhost", SessionTest)
    monkeypatch.setattr("database.SessionLocal", SessionTest)
    monkeypatch.setattr("database.get_db", lambda ws=None: SessionTest())

    return SessionTest


# --------------------------------------------------------------------------
# 1. get_chapter: async def & SSRF protection & event-loop safety
# --------------------------------------------------------------------------
def test_get_chapter_is_async_def():
    """get_chapter endpoint in threads.py must be an async def to prevent cross-event-loop Semaphore crashes."""
    from routers.threads import get_chapter
    assert inspect.iscoroutinefunction(get_chapter), (
        "get_chapter in routers/threads.py MUST be 'async def get_chapter', not sync 'def get_chapter'"
    )


def test_get_chapter_ssrf_blocked(test_db_setup, monkeypatch):
    """get_chapter must block on-demand scraping to private/loopback IP addresses."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ],
    )
    client = TestClient(app)
    response = client.get("/api/threads/1/chapters/1")
    assert response.status_code == 400
    assert "private or local network resources is forbidden" in response.json()["detail"]


# --------------------------------------------------------------------------
# 2. scrape.py endpoints: SSRF validation & SFACG routing & verify=True
# --------------------------------------------------------------------------
def test_scrape_import_url_ssrf_blocked(monkeypatch):
    """POST /api/threads/import-url must validate external URLs against SSRF."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 80))
        ],
    )
    client = TestClient(app)
    response = client.post("/api/threads/import-url", json={"url": "http://192.168.1.1/secret.html"})
    assert response.status_code == 400
    assert "private or local network resources is forbidden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scrape_import_url_routes_sfacg(test_db_setup, monkeypatch):
    """POST /api/threads/import-url with SFACG URL must route to SFACGAdapter."""
    from services.scrapers.sfacg import SFACGAdapter
    called = []

    async def mock_scrape_chapter(self, url):
        called.append(url)
        return ("第一章 SFACG Title", "Clean content from SFACG")

    monkeypatch.setattr(SFACGAdapter, "scrape_chapter_content", mock_scrape_chapter)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.21.5.10", 80))
        ],
    )

    client = TestClient(app)
    response = client.post(
        "/api/threads/import-url",
        json={"url": "https://book.sfacg.com/vip/c/779207/12345/"}
    )
    assert response.status_code == 200
    assert len(called) == 1
    assert "779207" in called[0]


def test_sfacg_adapter_metadata_verify_ssl():
    """SFACGAdapter.scrape_metadata must not disable TLS verification with verify=False."""
    import services.scrapers.sfacg as sfacg_module
    source_code = inspect.getsource(sfacg_module.SFACGAdapter.scrape_metadata)
    assert "verify=False" not in source_code, (
        "SFACGAdapter.scrape_metadata must not contain verify=False"
    )


# --------------------------------------------------------------------------
# 3. Dual-DB in-memory isolation (ACTIVE_IMAGE_JOBS, active_tasks, system.py)
# --------------------------------------------------------------------------
def test_active_image_jobs_workspace_isolation():
    """ACTIVE_IMAGE_JOBS must be queried with compound key (ws, thread_id) in get_thread_image_cache_status."""
    import routers.images as img_router
    source_code = inspect.getsource(img_router.get_thread_image_cache_status)
    assert "ACTIVE_IMAGE_JOBS.get(thread_id)" not in source_code, (
        "ACTIVE_IMAGE_JOBS.get(thread_id) fails to isolate thread status by workspace"
    )


def test_active_tasks_does_not_use_integer_alias():
    """active_tasks in BackgroundTranslator must not set raw integer chapter_id as key."""
    import services.background_translator as bt_module
    source_code = inspect.getsource(bt_module.BackgroundTranslator._run_translation_internal)
    assert "active_tasks[chapter_id] = task" not in source_code, (
        "active_tasks[chapter_id] = task creates integer collisions across workspaces"
    )


def test_novalpie_helpers_accept_workspace():
    """get_scraper_concurrency and get_novalpie_auth_config must accept workspace parameter."""
    from services.scrapers.novalpie import get_scraper_concurrency, get_novalpie_auth_config
    sig_conc = inspect.signature(get_scraper_concurrency)
    sig_auth = inspect.signature(get_novalpie_auth_config)
    assert "workspace" in sig_conc.parameters, "get_scraper_concurrency must accept 'workspace'"
    assert "workspace" in sig_auth.parameters, "get_novalpie_auth_config must accept 'workspace'"


def test_switch_workspace_does_not_stop_all_batches_globally():
    """switch_workspace in system.py must not cancel all batches across all workspaces globally."""
    import routers.system as sys_module
    source_code = inspect.getsource(sys_module.switch_workspace_endpoint)
    assert "BackgroundTranslator.stop_all_batches()" not in source_code, (
        "switch_workspace_endpoint must not call stop_all_batches() globally"
    )


# --------------------------------------------------------------------------
# 4. EPUB Image Extraction: Preserves subfolder unique names & extracts synopsis/cover
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_epub_image_extraction_unique_subfolders(test_db_setup, tmp_path, monkeypatch):
    """
    EPUB images in different subdirectories with identical filenames (e.g. OEBPS/ch1/001.jpg and OEBPS/ch2/001.jpg)
    must not overwrite each other.
    """
    import ebooklib
    from ebooklib import epub
    from routers.epub import upload_epub

    book = epub.EpubBook()
    book.set_title("Test Multi-Image Book")
    book.add_author("Author X")
    book.add_metadata("DC", "description", "This is the novel synopsis from metadata.")

    # Two images with same basename '001.jpg' in different subfolders
    img1 = epub.EpubItem(
        uid="img1",
        file_name="OEBPS/ch1/001.jpg",
        media_type="image/jpeg",
        content=b"\xff\xd8\xff" + b"IMAGE_CONTENT_1",
    )
    img2 = epub.EpubItem(
        uid="img2",
        file_name="OEBPS/ch2/001.jpg",
        media_type="image/jpeg",
        content=b"\xff\xd8\xff" + b"IMAGE_CONTENT_2",
    )
    book.add_item(img1)
    book.add_item(img2)

    # Add a chapter referencing images
    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = b"<html><body><p>Chapter 1 text</p><img src='ch1/001.jpg'/></body></html>"
    book.add_item(c1)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', c1]

    epub_bytes = io.BytesIO()
    epub.write_epub(epub_bytes, book)
    epub_bytes.seek(0)

    from fastapi import UploadFile
    upload_file = UploadFile(filename="test.epub", file=epub_bytes)

    import shutil
    with test_db_setup() as db:
        res = await upload_epub(file=upload_file, db=db)
        thread_id = res.thread_id
        thread = db.get(Thread, thread_id)
        assert thread.synopsis == "This is the novel synopsis from metadata."

        thread_img_dir = os.path.join("uploads", "images", f"thread_{thread_id}")
        assert os.path.exists(thread_img_dir)
        try:
            files = os.listdir(thread_img_dir)
            # Both image files must exist and neither should have been overwritten!
            assert len(files) == 2, f"Expected 2 image files in {thread_img_dir}, found: {files}"
        finally:
            shutil.rmtree(thread_img_dir, ignore_errors=True)


# --------------------------------------------------------------------------
# 5. Settings Masking: Masked cookie must not be saved to SQLite
# --------------------------------------------------------------------------
def test_settings_masked_cookie_not_saved_to_sqlite(test_db_setup):
    """When frontend submits masked novalpie_cookie, SQLite global_settings.novalpie_cookie must stay empty."""
    client = TestClient(app)
    # User updates settings with masked cookie
    response = client.post("/api/settings", json={
        "display_mode": "original",
        "novalpie_cookie": "eyJh...1234",  # masked string
    })
    assert response.status_code == 200

    with test_db_setup() as db:
        gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
        assert gs.novalpie_cookie == "", (
            f"SQLite leaked masked cookie string! Found: '{gs.novalpie_cookie}'"
        )


def test_create_safe_async_client_defaults_follow_redirects():
    """create_safe_async_client must enable follow_redirects=True by default to prevent silent 3xx failures."""
    from services.security import create_safe_async_client
    client = create_safe_async_client()
    assert client.follow_redirects is True


def test_start_thread_image_cache_strictly_workspace_isolated():
    """start_thread_image_cache must not fall back to unisolated integer thread_id."""
    import routers.images as img_router
    source_code = inspect.getsource(img_router.start_thread_image_cache)
    assert "ACTIVE_IMAGE_JOBS.get(thread_id)" not in source_code


@pytest.mark.asyncio
async def test_epub_image_extraction_path_traversal_blocked(test_db_setup, monkeypatch):
    """EPUB with malicious path traversal in image filename (e.g. '..') must be blocked."""
    import ebooklib
    from ebooklib import epub
    from routers.epub import upload_epub

    book = epub.EpubBook()
    book.set_title("Traversal Test Book")

    class MaliciousImageItem:
        def get_type(self):
            return ebooklib.ITEM_IMAGE
        def get_name(self):
            return ".."
        def get_content(self):
            return b"MALICIOUS_CONTENT"

    orig_read_epub = epub.read_epub
    def mock_read_epub(*args, **kwargs):
        b = orig_read_epub(*args, **kwargs)
        b.get_items_of_type = lambda t: [MaliciousImageItem()] if t == ebooklib.ITEM_IMAGE else []
        return b

    monkeypatch.setattr("routers.epub.epub.read_epub", mock_read_epub)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav']

    epub_bytes = io.BytesIO()
    epub.write_epub(epub_bytes, book)
    epub_bytes.seek(0)

    from fastapi import UploadFile
    upload_file = UploadFile(filename="evil.epub", file=epub_bytes)

    import shutil
    with test_db_setup() as db:
        res = await upload_epub(file=upload_file, db=db)
        thread_img_dir = os.path.join("uploads", "images", f"thread_{res.thread_id}")
        try:
            if os.path.exists(thread_img_dir):
                files = os.listdir(thread_img_dir)
                assert ".." not in files
                assert len(files) == 0
        finally:
            shutil.rmtree(thread_img_dir, ignore_errors=True)

