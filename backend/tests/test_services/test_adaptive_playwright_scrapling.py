import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bs4 import BeautifulSoup
from fastapi import HTTPException

from services.scrapers.adaptive_dom import AdaptiveDOM, AdaptivePage
from services.scrapers.novalpie import (
    NovalpieAdapter,
    _is_cloudflare_challenge,
    _install_resource_shield,
    _try_solve_cloudflare_turnstile,
    _attach_xhr_chapter_capture,
)
from services.scrapers.stealth_base import StealthyNovelAdapter
from routers.scrape import html_to_markdown, fetch_html_adaptive


def test_adaptive_dom_relocates_after_website_redesign(tmp_path: Path):
    """
    When a website changes its CSS classes and IDs (e.g. #chapter-101 .reader-content
    becomes <section class='ep-box-v3'>), AdaptiveDOM must relocate the content container
    using the saved structural signature.
    """
    store_file = tmp_path / "adaptive_selectors.json"

    html_v1 = """
    <html>
      <body>
        <header class="site-header"><a href="/">Home</a><a href="/catalog">Catalog</a></header>
        <main class="reader-layout">
          <article class="reader-content" id="chapter-101" data-chapter-id="101">
            <h2 class="chapter-title">第1章 觉醒之日</h2>
            <p>第一段：林恩睁开眼睛，发现自己身处一座古老的图书馆中。</p>
            <p>第二段：窗外的霓虹灯光穿透雨幕，映照在斑驳的石桌上。</p>
            <p>第三段：他伸出手，触摸到了那本散发着微光的秘典。</p>
          </article>
        </main>
        <footer class="site-footer">Copyright 2026</footer>
      </body>
    </html>
    """
    soup_v1 = BeautifulSoup(html_v1, "html.parser")
    el_v1 = AdaptiveDOM.select_one(
        soup_v1,
        ["#chapter-101", "article.reader-content"],
        domain="example-novel.org",
        key="chapter_content",
        role="content",
        adaptive=True,
        auto_save=True,
        store_path=store_file,
    )
    assert el_v1 is not None
    assert el_v1.get("id") == "chapter-101"
    assert store_file.exists()

    html_v2 = """
    <html>
      <body>
        <nav class="top-nav"><a href="/1">Link 1</a><a href="/2">Link 2</a><a href="/3">Link 3</a></nav>
        <main class="reader-layout">
          <section class="ep-box-v3" data-ep-index="102">
            <h2 class="ep-heading">第2章 禁忌契约</h2>
            <p>第一段：图书馆深处传来低沉的钟声，仿佛来自远古的呼唤。</p>
            <p>第二段：书页无风自动，金色的符文在空气中缓缓浮现。</p>
            <p>第三段：“你终于来了，”一道苍老的声音在脑海中响起。</p>
          </section>
        </main>
        <aside class="sidebar-ads"><a href="/ad1">Buy Coins</a><a href="/ad2">Download App</a></aside>
      </body>
    </html>
    """
    soup_v2 = BeautifulSoup(html_v2, "html.parser")
    el_v2 = AdaptiveDOM.select_one(
        soup_v2,
        ["#chapter-101", "article.reader-content"],
        domain="example-novel.org",
        key="chapter_content",
        role="content",
        adaptive=True,
        auto_save=False,
        store_path=store_file,
    )
    assert el_v2 is not None
    assert el_v2.name == "section"
    assert "ep-box-v3" in el_v2.get("class", [])
    assert "图书馆深处传来低沉的钟声" in el_v2.get_text()
    assert "Buy Coins" not in el_v2.get_text()


def test_novalpie_parse_chapter_html_adaptive_on_redesigned_dom():
    """
    NovalpieAdapter._parse_chapter_html must extract clean chapter title & text
    without leaking navbar/sidebar noise even if #chapter-{id} and .reader-content are renamed.
    """
    adapter = NovalpieAdapter(workspace="main")
    redesigned_html = """
    <html>
      <head><title>Site Wrapper Title</title></head>
      <body>
        <nav class="global-nav"><a href="/login">登录</a><a href="/rank">排行榜</a></nav>
        <div class="layout-shell">
          <div class="custom-novel-body-v4">
            <h1>第 15 章 星海彼岸</h1>
            <p>星舰缓缓驶出跃迁通道，眼前的星云如同燃烧的琥珀。</p>
            <p>舰长站在指挥台上，目光凝视着远方未知的轨道空间站。</p>
            <p>“全员准备接驳，”他沉声下达了最后的指令。</p>
          </div>
        </div>
        <footer>关于我们 | 联系方式</footer>
      </body>
    </html>
    """
    title, content = adapter._parse_chapter_html(redesigned_html, chapter_id=99999)
    assert "第 15 章 星海彼岸" in title
    assert "星舰缓缓驶出跃迁通道" in content
    assert "排行榜" not in content
    assert "关于我们" not in content


def test_playwright_resource_shield_blocks_fonts_and_trackers_but_allows_images():
    """_install_resource_shield must abort fonts/media/trackers while continuing chapter images."""
    mock_page = MagicMock()
    registered_handler = {}

    def capture_route(pattern, handler):
        registered_handler["fn"] = handler

    mock_page.route.side_effect = capture_route
    _install_resource_shield(mock_page, disable_resources=True)
    handler = registered_handler["fn"]

    font_route = MagicMock()
    font_route.request.resource_type = "font"
    font_route.request.url = "https://novalpie.cc/fonts/custom.woff2"
    handler(font_route)
    font_route.abort.assert_called_once()

    tracker_route = MagicMock()
    tracker_route.request.resource_type = "script"
    tracker_route.request.url = "https://www.google-analytics.com/analytics.js"
    handler(tracker_route)
    tracker_route.abort.assert_called_once()

    img_route = MagicMock()
    img_route.request.resource_type = "image"
    img_route.request.url = "https://images.novelpia.com/imagebox/ab/abcdef.jpg"
    handler(img_route)
    img_route.continue_.assert_called_once()
    img_route.abort.assert_not_called()


def test_active_cloudflare_turnstile_solver_clicks_iframe_or_box():
    """_try_solve_cloudflare_turnstile must click Turnstile checkbox inside challenge frame or bounding box."""
    assert _is_cloudflare_challenge("<html><title>Just a moment...</title></html>") is True
    assert _is_cloudflare_challenge("<html><body>Normal Chapter Content</body></html>") is False

    mock_page = MagicMock()
    mock_page.frames = []
    mock_el = MagicMock()
    mock_el.bounding_box.return_value = {"x": 100.0, "y": 200.0, "width": 300.0, "height": 65.0}
    mock_page.query_selector.return_value = mock_el

    solved = _try_solve_cloudflare_turnstile(mock_page)
    assert solved is True
    mock_page.mouse.click.assert_called_once()


def test_xhr_chapter_capture_intercepts_json_payload():
    """_attach_xhr_chapter_capture must capture decrypted chapter text and title from /api/ JSON responses."""
    mock_page = MagicMock()
    listeners = {}

    def on_event(event_name, callback):
        listeners[event_name] = callback

    mock_page.on.side_effect = on_event
    captured = _attach_xhr_chapter_capture(mock_page, chapter_id=5831032)

    mock_resp = MagicMock()
    mock_resp.url = "https://novalpie.cc/api/chapters/5831032/content"
    mock_resp.headers = {"content-type": "application/json; charset=utf-8"}
    mock_resp.json.return_value = {
        "data": {
            "title": "第1章 赛博巨龙",
            "content": "这是一段超过一百个字符的真实章节正文内容。" * 8,
        }
    }
    listeners["response"](mock_resp)
    assert captured["title"] == "第1章 赛博巨龙"
    assert len(captured["content"]) > 100


def test_stealth_base_adaptive_page_and_native_fallback():
    """StealthyNovelAdapter.extract_clean_chapter must work with AdaptivePage and relocate selectors."""
    html = """
    <html>
      <body>
        <div class="new-chapter-box">
          <h1 class="new-heading">Chapter 42: Adaptive Victory</h1>
          <p>The old #chapter-content selector was removed by the site owner.</p>
          <p>Yet AdaptivePage relocated the prose container automatically without Scrapling installed.</p>
        </div>
      </body>
    </html>
    """
    page = AdaptivePage(html=html, url="https://novel-example.com/ch/42")
    title, md = StealthyNovelAdapter.extract_clean_chapter(
        page,
        title_selector="h1.old-missing-title",
        content_selector="#old-missing-content",
        adaptive=True,
        auto_save=True,
    )
    assert title == "Chapter 42: Adaptive Victory"
    assert "AdaptivePage relocated the prose container automatically" in md


@pytest.mark.asyncio
async def test_fetch_html_adaptive_ssrf_and_playwright_escalation(monkeypatch):
    """fetch_html_adaptive must block private IPs and escalate Cloudflare challenge pages to StealthyNovelAdapter."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    )
    with pytest.raises(HTTPException) as exc_info:
        await fetch_html_adaptive("http://127.0.0.1:8000/secret")
    assert exc_info.value.status_code == 400

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.21.5.10", 443))],
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><title>Just a moment...</title><div class='cf-browser-verification'></div></html>"
    mock_resp.url = "https://protected-novel.example/ch/1"
    mock_resp.raise_for_status = lambda: None

    mock_stealth_page = MagicMock()
    mock_stealth_page.html = "<html><title>Chapter 1</title><article><p>Decrypted novel content after Turnstile solve.</p></article></html>"
    mock_stealth_page.url = "https://protected-novel.example/ch/1"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        with patch.object(StealthyNovelAdapter, "fetch_stealth_page", new_callable=AsyncMock, return_value=mock_stealth_page) as mock_pw:
            html_out, _ = await fetch_html_adaptive("https://protected-novel.example/ch/1", workspace="main")
            assert "Decrypted novel content after Turnstile solve." in html_out
            mock_pw.assert_called_once()
