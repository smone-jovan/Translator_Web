import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from services.scrapers.novalpie import NovalpieAdapter
from services.scrapers.engine import MetadataScraperEngine

def test_extract_novel_id():
    adapter = NovalpieAdapter()
    assert adapter.extract_novel_id("https://novalpie.cc/book/12345") == 12345
    assert adapter.extract_novel_id("https://novalpie.cc/novel/67890") == 67890
    assert adapter.extract_novel_id("https://novalpie.cc/read/12345/67890") == 12345
    assert adapter.extract_novel_id("https://novalpie.cc/999") == 999
    assert adapter.extract_novel_id("12345") == 12345
    assert adapter.extract_novel_id("invalid-text") is None

def test_extract_chapter_id():
    adapter = NovalpieAdapter()
    assert adapter.extract_chapter_id("https://novalpie.cc/read/12345/67890") == 67890
    assert adapter.extract_chapter_id("https://novalpie.cc/chapter/999") == 999
    assert adapter.extract_chapter_id("https://novalpie.cc/book/12345") is None

@pytest.mark.asyncio
async def test_scrape_metadata_success():
    adapter = NovalpieAdapter()
    mock_payload = {
        "success": True,
        "data": {
            "title": "I Became the Academy Villain",
            "author": "Novelpia Writer",
            "description": "A thrilling fantasy academy novel.",
            "tags": ["Fantasy", "Academy", "Harem"],
            "cover_image": "https://images.novelpia.com/cover/12345.jpg",
            "status": "Ongoing"
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        meta = await adapter.scrape_metadata("https://novalpie.cc/book/12345")
        
        assert meta.success is True
        assert meta.title == "I Became the Academy Villain"
        assert meta.author == "Novelpia Writer"
        assert meta.synopsis == "A thrilling fantasy academy novel."
        assert "Fantasy" in meta.genres
        assert meta.cover_image == "https://images.novelpia.com/cover/12345.jpg"
        assert meta.detail_url == "https://novalpie.cc/book/12345"

@pytest.mark.asyncio
async def test_scrape_toc_success():
    adapter = NovalpieAdapter()
    mock_meta = {
        "success": True,
        "data": {"title": "Academy Survival Guide"}
    }
    mock_chapters = {
        "success": True,
        "chapters": [
            {"id": 101, "chapter_number": 1, "title": "Prologue"},
            {"id": 102, "chapter_number": 2, "title": "Entrance Ceremony"}
        ]
    }

    async def custom_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "detail" in url:
            resp.json.return_value = mock_meta
        else:
            resp.json.return_value = mock_chapters
        return resp

    with patch("httpx.AsyncClient.get", side_effect=custom_get):
        title, chapters = await adapter.scrape_toc("https://novalpie.cc/book/555")
        assert title == "Academy Survival Guide"
        assert len(chapters) == 2
        assert chapters[0]["chapter_id"] == 101
        assert "Prologue" in chapters[0]["title"]
        assert chapters[0]["url"] == "https://novalpie.cc/book/555/101"

@pytest.mark.asyncio
async def test_engine_routing():
    engine = MetadataScraperEngine()
    assert "novalpie" in engine.adapters
    
    mock_meta_res = MagicMock()
    mock_meta_res.success = True
    mock_meta_res.title = "Novalpie Hit"

    with patch.object(engine.adapters["novalpie"], "scrape_metadata", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = mock_meta_res
        res = await engine.scrape("https://novalpie.cc/book/777", source="novalpie")
        assert res.title == "Novalpie Hit"
        mock_scrape.assert_called_once()

@pytest.mark.asyncio
async def test_scrape_chapter_content_direct_playwright():
    adapter = NovalpieAdapter()
    
    mock_html = """
    <article class="reader-content">
        <div id="chapter-67890" class="chapter-item">
            <div class="chapter-separator"><h2>Chapter 1: The Beginning</h2></div>
            <div>
                <p>This is the first paragraph.</p>
                <p>This is the second paragraph.</p>
                <script>alert(1)</script>
            </div>
        </div>
    </article>
    """
    
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_pw:
        mock_pw.return_value = mock_html
        title, content = await adapter.scrape_chapter_content("https://novalpie.cc/read/12345/67890")
        
        assert title == "Chapter 1: The Beginning"
        assert "This is the first paragraph." in content
        assert "This is the second paragraph." in content
        assert "script" not in content

def test_parse_chapter_html_isolates_requested_chapter():
    adapter = NovalpieAdapter()
    raw_html = """
    <article class="reader-content">
        <div id="chapter-101" class="chapter-item">
            <div class="chapter-separator"><h2>Chapter 101</h2></div>
            <div>This is Chapter 101 text.</div>
            <div class="chapter-comments">Comments 101</div>
        </div>
        <div id="chapter-102" class="chapter-item">
            <div class="chapter-separator"><h2>Chapter 102</h2></div>
            <div>This is Chapter 102 target text.</div>
            <div class="chapter-comments">Comments 102</div>
        </div>
        <div id="chapter-103" class="chapter-item">
            <div class="chapter-separator"><h2>Chapter 103</h2></div>
            <div>This is Chapter 103 text.</div>
        </div>
    </article>
    """
    title, content = adapter._parse_chapter_html(raw_html, chapter_id=102)
    assert title == "Chapter 102"
    assert "Chapter 102 target text." in content
    assert "Chapter 101" not in content
    assert "Chapter 103" not in content
    assert "Comments" not in content

def test_parse_chapter_html_preserves_images_in_place():
    adapter = NovalpieAdapter()
    raw_html = """
    <div id="chapter-200" class="chapter-item">
        <div class="chapter-separator"><h2>Illustration Chapter</h2></div>
        <div>
            Before image text.
            <div class="image-wrapper is-loaded">
                <div class="loading-placeholder">图片加载中...</div>
                <div class="error-placeholder">⚠️ 图片加载失败</div>
                <img src="https://images.novelpia.com/cover/test_ill.file" class="chapter-image" alt="插图1">
            </div>
            After image text.
        </div>
    </div>
    """
    title, content = adapter._parse_chapter_html(raw_html, chapter_id=200)
    assert title == "Illustration Chapter"
    assert "Before image text." in content
    assert "![插图1](https://images.novelpia.com/cover/test_ill.file)" in content
    assert "After image text." in content
    assert "图片加载" not in content
    assert "⚠️" not in content

def test_parse_chapter_html_strips_vue_artifacts():
    adapter = NovalpieAdapter()
    raw_html = """
    <div id="chapter-300" class="chapter-item">
        <div class="chapter-separator"><h2>Clean Chapter</h2></div>
        <div>
            封面折叠
            Actual novel line 1.
            <br><br>
            Actual novel line 2.
        </div>
        <div class="chapter-comments">
            <button>展开评论 (5)</button>
        </div>
    </div>
    """
    title, content = adapter._parse_chapter_html(raw_html, chapter_id=300)
    assert title == "Clean Chapter"
    assert "封面折叠" not in content
    assert "展开评论" not in content
    assert "Actual novel line 1." in content
    assert "Actual novel line 2." in content


def test_parse_chapter_html_rejects_rate_limit_error():
    adapter = NovalpieAdapter()
    raw_html = """
    <div id="chapter-500" class="chapter-item">
        <div class="chapter-separator"><h2>Chapter 500</h2></div>
        <div>
            加载章节内容失败：请求过于频繁，请稍后再试。请重试。
        </div>
    </div>
    """
    title, content = adapter._parse_chapter_html(raw_html, chapter_id=500)
    assert content == ""


@pytest.mark.asyncio
async def test_scrape_chapter_content_playwright_retry():
    adapter = NovalpieAdapter()

    mock_html = """
    <article class="reader-content">
        <div id="chapter-67890" class="chapter-item">
            <div class="chapter-separator"><h2>Retry Success Title</h2></div>
            <div><p>Retry Success Content</p></div>
        </div>
    </article>
    """
    
    attempts = 0
    def mock_run_pw(func, url):
        nonlocal attempts
        attempts += 1
        return mock_html

    with patch("asyncio.to_thread", side_effect=mock_run_pw):
        title, content = await adapter.scrape_chapter_content("https://novalpie.cc/read/12345/67890")
        assert title == "Retry Success Title"
        assert "Retry Success Content" in content
        assert attempts == 1


def test_get_novalpie_auth_config():
    from services.scrapers.novalpie import get_novalpie_auth_config
    
    # 1. Disabled / default
    with patch("database.SessionLocal") as mock_db_cls, patch("services.ai.secrets.load_secrets", return_value={"novalpie_cookie": ""}):
        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__.return_value = mock_db
        mock_gs = MagicMock()
        mock_gs.novalpie_auth_enabled = 0
        mock_gs.novalpie_cookie = ""
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_gs
        
        enabled, raw, token, pw_cookies = get_novalpie_auth_config()
        assert enabled is False
        assert token == ""
        assert len(pw_cookies) == 0

    # 2. Enabled with plain token in secrets (.env)
    with patch("database.SessionLocal") as mock_db_cls, patch("services.ai.secrets.load_secrets", return_value={"novalpie_cookie": "secret_jwt_token_123"}):
        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__.return_value = mock_db
        mock_gs = MagicMock()
        mock_gs.novalpie_auth_enabled = 1
        mock_gs.novalpie_cookie = ""
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_gs
        
        enabled, raw, token, pw_cookies = get_novalpie_auth_config()
        assert enabled is True
        assert token == "secret_jwt_token_123"
        assert len(pw_cookies) == 2
        assert pw_cookies[0]["name"] == "auth_token"
        assert pw_cookies[0]["value"] == "secret_jwt_token_123"

    # 3. Enabled with cookie string
    with patch("database.SessionLocal") as mock_db_cls, patch("services.ai.secrets.load_secrets", return_value={"novalpie_cookie": "session_id=xyz789; auth_token=token_abc_456; other=foo"}):
        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__.return_value = mock_db
        mock_gs = MagicMock()
        mock_gs.novalpie_auth_enabled = 1
        mock_gs.novalpie_cookie = ""
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_gs
        
        enabled, raw, token, pw_cookies = get_novalpie_auth_config()
        assert enabled is True
        assert token == "token_abc_456"
        assert len(pw_cookies) == 6

    # 4. Enabled with raw tab-separated DevTools table (Novelpia)
    with patch("database.SessionLocal") as mock_db_cls, patch("services.ai.secrets.load_secrets", return_value={"novalpie_cookie": "LOGINKEY\t821b821d_secret\t.novelpia.com\t/\nUSERKEY\tc8bc893c_user\t.novelpia.com\t/"}):
        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__.return_value = mock_db
        mock_gs = MagicMock()
        mock_gs.novalpie_auth_enabled = 1
        mock_gs.novalpie_cookie = ""
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_gs
        
        enabled, raw, token, pw_cookies = get_novalpie_auth_config()
        assert enabled is True
        assert "821b821d_secret" in token or "c8bc893c_user" in token
        assert "LOGINKEY=821b821d_secret" in raw
        assert "USERKEY=c8bc893c_user" in raw


def test_adapter_get_request_headers_dual_mode():
    adapter = NovalpieAdapter()
    
    # Guest mode
    with patch("services.scrapers.novalpie.get_novalpie_auth_config", return_value=(False, "", "", [])):
        headers = adapter.get_request_headers()
        assert "Authorization" not in headers
        assert "Cookie" not in headers

    # Authenticated mode
    with patch("services.scrapers.novalpie.get_novalpie_auth_config", return_value=(True, "auth_token=tok123", "tok123", [{"name": "auth_token", "value": "tok123"}])):
        headers = adapter.get_request_headers()
        assert headers.get("Authorization") == "Bearer tok123"
        assert "auth_token=tok123" in headers.get("Cookie", "")


def test_parse_chapter_html_normalizes_image_urls():
    adapter = NovalpieAdapter()
    raw_html = """
    <article class="reader-content">
        <h2>Chapter with Images</h2>
        <p>Text line 1</p>
        <div class="image-wrapper">
            <img src="//images.novelpia.com/content/img1.png" alt="Illust 1">
        </div>
        <p>Text line 2</p>
        <img src="/assets/novalpie.cc/img2.jpg" alt="Illust 2">
        <p>Text line 3</p>
        <img src="https://jpg.freenovel.sbs/6e278b9fcdf8f356139dfeb0cbe268fe_351694_ori.file" alt="Illust 3">
        <p>Text line 4</p>
        <img src="https://novelkit.top/images/ab12345678_ori.file" alt="Illust 4">
        <p>Text line 5 with placeholder [[img:9876543210_test.file]]</p>
        <p>Text line 6 with [图片: https://images.novelpia.com/tupian_test.jpg]</p>
        <p>Text line 7 with raw “https://images.novelpia.com/imageops/quoted_test.png” in text</p>
    </article>
    """
    title, content = adapter._parse_chapter_html(raw_html, chapter_id=999)
    assert title == "Chapter with Images"
    assert "![Illust 1](https://images.novelpia.com/content/img1.png)" in content
    assert "![Illust 2](https://novalpie.cc/assets/novalpie.cc/img2.jpg)" in content
    assert "![Illust 3](https://images.novelpia.com/imagebox/6e/6e278b9fcdf8f356139dfeb0cbe268fe_351694_ori.file)" in content
    assert "![Illust 4](https://images.novelpia.com/imagebox/ab/ab12345678_ori.file)" in content
    assert "![插图](https://images.novelpia.com/imagebox/98/9876543210_test.file)" in content
    assert "![插图](https://images.novelpia.com/tupian_test.jpg)" in content
    assert "![插图](https://images.novelpia.com/imageops/quoted_test.png)" in content



@pytest.mark.asyncio
async def test_scrape_metadata_adult_verification_gives_actionable_message():
    adapter = NovalpieAdapter()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {
        "success": False,
        "error_code": "ADULT_VERIFICATION_REQUIRED",
        "require_verification": True,
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        meta = await adapter.scrape_metadata("https://novalpie.cc/book/350000")

    assert meta.success is False
    assert "ADULT_VERIFICATION_REQUIRED" in meta.synopsis
    assert "Novalpie" in meta.synopsis and "workspace" in meta.synopsis.lower()


def test_sync_shared_settings_copies_novalpie_auth_flag_to_ghost():
    from types import SimpleNamespace
    from database import sync_shared_settings_to_ghost

    names = ("openai_api_key", "gemini_api_key", "openrouter_api_key", "openai_api_keys",
             "gemini_api_keys", "openrouter_api_keys", "llm_provider", "openai_model",
             "gemini_model", "openrouter_model", "ghost_pin")
    main = SimpleNamespace(**{n: f"main-{n}" for n in names}, novalpie_auth_enabled=1)
    ghost = SimpleNamespace(**{n: "old" for n in names}, novalpie_auth_enabled=0)

    sync_shared_settings_to_ghost(main, ghost)

    assert ghost.novalpie_auth_enabled == 1
    assert ghost.ghost_pin == "main-ghost_pin"
