import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
from fastapi.testclient import TestClient
import pytest
from main import app
from database import get_db, Thread, Chapter
from services.image_cacher import CACHE_DIR, guess_image_ext_from_bytes, is_safe_cache_path


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_guess_image_ext():
    assert guess_image_ext_from_bytes(b"\x89PNG\r\n\x1a\n123") == "png"
    assert guess_image_ext_from_bytes(b"\xff\xd8\xff\xe0") == "jpeg"
    assert guess_image_ext_from_bytes(b"RIFF\x00\x00\x00\x00WEBP") == "webp"
    assert guess_image_ext_from_bytes(b"GIF89a\x01\x00") == "gif"
    assert guess_image_ext_from_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'>") == "svg+xml"


def test_path_safety():
    assert is_safe_cache_path(CACHE_DIR / "safe_file.png") is True
    assert is_safe_cache_path(Path("C:/Windows/System32/cmd.exe")) is False
    assert is_safe_cache_path(CACHE_DIR / ".." / ".." / "database.py") is False


def test_proxy_image_security_and_validation(client):
    # Reject invalid protocol
    res = client.get("/api/images/proxy?url=ftp://evil.com/img.png")
    assert res.status_code == 400

    # Reject relative path
    res = client.get("/api/images/proxy?url=/images/local.png")
    assert res.status_code == 400

    # Reject dummy domain
    res = client.get("/api/images/proxy?url=https://example.com/test.png")
    assert res.status_code == 404


def test_proxy_image_hit(client):
    dummy_url = "https://cdn.example-novel.org/art/chapter1.png"
    url_hash = hashlib.sha256(dummy_url.encode("utf-8")).hexdigest()
    fake_png = b"\x89PNG\r\n\x1a\nFAKEPNGDATA"
    cache_path = CACHE_DIR / f"{url_hash}.png"
    cache_path.write_bytes(fake_png)

    try:
        with patch("services.security.validate_external_url"):
            res = client.get(f"/api/images/proxy?url={dummy_url}")
        assert res.status_code == 200
        assert res.headers.get("x-cache-status") == "HIT"
        assert res.headers.get("content-type") == "image/png"
        assert res.content == fake_png
    finally:
        if cache_path.exists():
            cache_path.unlink()


def test_proxy_image_miss_and_fetch(client):
    remote_url = "https://mocked-site.org/illustration.webp"
    fake_webp = b"RIFF\x00\x00\x00\x00WEBPVP8X"
    url_hash = hashlib.sha256(remote_url.encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"{url_hash}.webp"

    mock_resp = httpx.Response(
        status_code=200,
        content=fake_webp,
        request=httpx.Request("GET", remote_url)
    )

    with patch("services.security.validate_external_url"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = client.get(f"/api/images/proxy?url={remote_url}")
        assert res.status_code == 200
        assert res.headers.get("x-cache-status") == "MISS"
        assert res.content == fake_webp
        assert cache_file.exists()

    if cache_file.exists():
        cache_file.unlink()


def test_thread_cache_images_workflow(client, db_session):
    thread = Thread(title="Illustrated Test Novel")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    ch1 = Chapter(
        thread_id=thread.id,
        title_original="Ch 1",
        content_original="Look here: ![Hero](https://novel.org/art1.jpg)\nAnd <img src=\"https://novel.org/art2.png\" />",
        order=1
    )
    ch2 = Chapter(
        thread_id=thread.id,
        title_original="Ch 2",
        content_original="Just text no images",
        order=2
    )
    db_session.add_all([ch1, ch2])
    db_session.commit()

    # Initial status
    res = client.get(f"/api/threads/{thread.id}/cache-images/status")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert data["cached"] == 0

    # Start caching
    with patch("services.image_cacher.run_thread_image_caching_job", new_callable=AsyncMock) as mock_run:
        post_res = client.post(f"/api/threads/{thread.id}/cache-images")
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["status"] == "started"
        assert post_data["total"] == 2


def test_cache_stats_and_clear_endpoint(client):
    dummy_file = CACHE_DIR / "stat_test.png"
    dummy_file.write_bytes(b"\x89PNG\r\n\x1a\n1234567890")

    try:
        res = client.get("/api/cache/images/stats")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] >= 1
        assert data["total_bytes"] >= 18

        clear_res = client.post("/api/cache/images/clear")
        assert clear_res.status_code == 200
        clear_data = clear_res.json()
        assert clear_data["status"] == "success"
        assert clear_data["deleted_count"] >= 1

        # Check stats after clear
        res_after = client.get("/api/cache/images/stats")
        assert res_after.status_code == 200
        assert res_after.json()["count"] == 0
        assert res_after.json()["total_bytes"] == 0
    finally:
        if dummy_file.exists():
            dummy_file.unlink()


def test_list_thread_images(client, db_session):
    thread = Thread(title="Gallery Test Novel")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    ch1 = Chapter(
        thread_id=thread.id,
        title_original="Original Title 1",
        title_translated="Bab 1: Awal Petualangan",
        content_original="Here is art: ![Cover Art](https://novel.org/img1.jpg)\nAnd another: <img src=\"https://novel.org/img2.png\" alt=\"Portrait\" />",
        order=1
    )
    ch2 = Chapter(
        thread_id=thread.id,
        title_original="Bab 2",
        content_original="No images here.",
        order=2
    )
    db_session.add_all([ch1, ch2])
    db_session.commit()

    res = client.get(f"/api/threads/{thread.id}/images")
    assert res.status_code == 200
    data = res.json()
    assert data["thread_id"] == thread.id
    assert data["total_images"] == 2
    assert len(data["images"]) == 2
    assert data["images"][0]["url"] == "https://novel.org/img1.jpg"
    assert data["images"][0]["alt"] == "Cover Art"
    assert data["images"][0]["chapter_order"] == 1
    assert data["images"][0]["chapter_title"] == "Bab 1: Awal Petualangan"
    assert data["images"][1]["url"] == "https://novel.org/img2.png"
    assert data["images"][1]["alt"] == "Portrait"


def test_proxy_image_force_refresh(client):
    target_url = "https://example-cdn.novel.org/art_force.png"
    url_hash = hashlib.sha256(target_url.encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"{url_hash}.png"

    # Seed old cache
    cache_file.write_bytes(b"\x89PNG\r\n\x1a\nOLD_DATA")
    try:
        # Without force -> HIT with old data
        with patch("services.security.validate_external_url"):
            res1 = client.get(f"/api/images/proxy?url={target_url}")
        assert res1.status_code == 200
        assert res1.headers.get("x-cache-status") == "HIT"
        assert res1.content == b"\x89PNG\r\n\x1a\nOLD_DATA"

        # With force=true -> bypasses cache and re-fetches
        with patch("services.security.validate_external_url"), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.content = b"\x89PNG\r\n\x1a\nNEW_FRESH_DATA"
            mock_get.return_value = mock_resp

            res2 = client.get(f"/api/images/proxy?url={target_url}&force=true")
            assert res2.status_code == 200
            assert res2.headers.get("x-cache-status") == "MISS"
            assert res2.content == b"\x89PNG\r\n\x1a\nNEW_FRESH_DATA"

            # Verify file on disk was replaced with fresh data
            assert cache_file.read_bytes() == b"\x89PNG\r\n\x1a\nNEW_FRESH_DATA"
    finally:
        if cache_file.exists():
            cache_file.unlink()
