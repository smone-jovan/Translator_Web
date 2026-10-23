"""
AdaptiveDOM selector signatures are isolated per workspace (ghost isolation invariant, R-12).
main keeps backend/data/adaptive_selectors.json (legacy entries still load); ghost uses its own
adaptive_selectors.ghost.json. The memory cache is keyed by workspace too, so a domain learned in
ghost never leaks into main, on disk or in memory. Every production caller passes workspace.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from bs4 import BeautifulSoup
from starlette.requests import Request

import routers.scrape as scrape_router
import routers.threads as threads_router
from database import Chapter, Thread
from services.scrapers import adaptive_dom
from services.scrapers.adaptive_dom import AdaptiveDOM, AdaptivePage

REAL_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SIG = {"tag": "article", "class_tokens": ["reader", "content"], "len_bucket": "long"}
DOMAIN = "private-novel.example"

_PROSE = "".join(
    f"<p>这是第{i}段正文，主角走进了房间。他看着窗外，心里想着明天的事情。</p>" for i in range(8)
)
CH1_URL = f"https://{DOMAIN}/book/1/1.html"
CH2_URL = f"https://{DOMAIN}/book/1/2.html"


def _chapter_html(title: str, next_href: str | None = None) -> str:
    nav = f"<a href='{next_href}'>下一章</a>" if next_href else ""
    return f"<html><body><h1>{title}</h1><div id='content'>{_PROSE}</div>{nav}</body></html>"


PAGES = {
    CH1_URL: (_chapter_html("第一章", "/book/1/2.html"), CH1_URL),
    CH2_URL: (_chapter_html("第二章 新的开始"), CH2_URL),
}


def _main_store() -> Path:
    return adaptive_dom._DEFAULT_STORE_PATH


def _ghost_store() -> Path:
    return adaptive_dom._GHOST_STORE_PATH


def _disk_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def _domain_keys(path: Path, domain: str = DOMAIN) -> set[str]:
    return {k for k in _disk_keys(path) if k.startswith(f"{domain}::")}


def _forget_memory() -> None:
    adaptive_dom._SIGNATURE_MEMORY_CACHE.clear()


def _fake_fetch(pages=PAGES) -> AsyncMock:
    async def fetch(url, *, workspace=None, allow_playwright_fallback=True):
        return pages[url]

    return AsyncMock(side_effect=fetch)


def _seed(db, *, workspace: str):
    db._workspace = workspace
    thread = Thread(title="Private Novel", source_url=CH1_URL)
    db.add(thread)
    db.commit()
    chapter = Chapter(thread_id=thread.id, order=1, title_original="第一章", content_original="x", source_url=CH1_URL)
    db.add(chapter)
    db.commit()
    return thread, chapter


def _assert_learned_only_in_ghost() -> None:
    assert _domain_keys(_main_store()) == set(), "ghost scrape leaked a selector record into the main store"
    assert _domain_keys(_ghost_store()), "ghost scrape did not learn anything in the ghost store"


# --- Store layer -----------------------------------------------------------------------------


def test_conftest_redirects_both_workspace_stores_away_from_real_files():
    assert _main_store().resolve() != (REAL_DATA_DIR / "adaptive_selectors.json").resolve()
    assert _ghost_store().resolve() != (REAL_DATA_DIR / "adaptive_selectors.ghost.json").resolve()
    assert _main_store().resolve() != _ghost_store().resolve()


@pytest.mark.parametrize("forget_memory", [False, True], ids=["memory-cache", "disk"])
def test_signature_saved_in_ghost_is_not_loaded_in_main(forget_memory):
    AdaptiveDOM.save_signature(DOMAIN, "content", SIG, workspace="ghost")
    if forget_memory:
        _forget_memory()

    assert AdaptiveDOM.load_signature(DOMAIN, "content", workspace="main") is None
    assert AdaptiveDOM.load_signature(DOMAIN, "content", workspace="ghost") == SIG


@pytest.mark.parametrize("forget_memory", [False, True], ids=["memory-cache", "disk"])
def test_signature_saved_in_main_is_not_loaded_in_ghost(forget_memory):
    AdaptiveDOM.save_signature(DOMAIN, "content", SIG, workspace="main")
    if forget_memory:
        _forget_memory()

    assert AdaptiveDOM.load_signature(DOMAIN, "content", workspace="ghost") is None
    assert AdaptiveDOM.load_signature(DOMAIN, "content", workspace="main") == SIG


def test_ghost_writes_go_to_ghost_file_and_leave_main_file_untouched():
    _main_store().parent.mkdir(parents=True, exist_ok=True)
    _main_store().write_text(json.dumps({"public.example::content": SIG}), encoding="utf-8")
    main_before = _main_store().read_bytes()

    AdaptiveDOM.save_signature(DOMAIN, "content", SIG, workspace="ghost")

    assert _main_store().read_bytes() == main_before
    assert _disk_keys(_ghost_store()) == {f"{DOMAIN}::content"}


def test_legacy_main_entries_still_load_in_main_but_not_in_ghost():
    _main_store().parent.mkdir(parents=True, exist_ok=True)
    _main_store().write_text(json.dumps({"legacy.example::content": SIG}), encoding="utf-8")

    assert AdaptiveDOM.load_signature("legacy.example", "content", workspace="main") == SIG
    assert AdaptiveDOM.load_signature("legacy.example", "content", workspace="ghost") is None


def test_explicit_store_path_overrides_workspace_store(tmp_path):
    custom = tmp_path / "custom" / "selectors.json"

    AdaptiveDOM.save_signature(DOMAIN, "content", SIG, workspace="ghost", store_path=custom)
    _forget_memory()

    assert _disk_keys(custom) == {f"{DOMAIN}::content"}
    assert not _ghost_store().exists()
    assert not _main_store().exists()
    assert AdaptiveDOM.load_signature(DOMAIN, "content", workspace="ghost", store_path=custom) == SIG


def test_select_one_learns_and_relocates_within_its_workspace_only():
    html_v1 = f"<html><body><article class='reader-content'>{_PROSE}</article></body></html>"
    html_v2 = f"<html><body><div class='ep-box'><section class='ep-body'>{_PROSE}</section></div></body></html>"
    AdaptiveDOM.select_one(
        BeautifulSoup(html_v1, "html.parser"), ["article.reader-content"],
        domain=DOMAIN, key="content", workspace="ghost",
    )

    _assert_learned_only_in_ghost()
    relocated = AdaptiveDOM.select_one(
        BeautifulSoup(html_v2, "html.parser"), ["article.reader-content"],
        domain=DOMAIN, key="content", adaptive=True, auto_save=False, workspace="ghost",
    )
    assert relocated is not None and "主角走进了房间" in relocated.get_text()


def test_adaptive_page_and_node_save_into_their_workspace():
    page = AdaptivePage(html=_chapter_html("第一章"), url=CH1_URL, workspace="ghost")

    nodes = page.css("#content", auto_save=True)
    nodes[0].css("p", auto_save=True)

    _assert_learned_only_in_ghost()
    assert {f"{DOMAIN}::#content", f"{DOMAIN}::p"} <= _disk_keys(_ghost_store())


# --- Production callers ----------------------------------------------------------------------


def test_html_to_markdown_in_ghost_saves_only_to_ghost_store():
    title, markdown = scrape_router.html_to_markdown(_chapter_html("第一章"), url=CH1_URL, workspace="ghost")

    assert title == "第一章" and "主角走进了房间" in markdown
    _assert_learned_only_in_ghost()
    assert {f"{DOMAIN}::title", f"{DOMAIN}::content"} <= _disk_keys(_ghost_store())


@pytest.mark.asyncio
async def test_scrape_route_in_ghost_learns_only_in_ghost(monkeypatch):
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch())

    await scrape_router.scrape_url_in_workspace(scrape_router.ScrapeRequest(url=CH1_URL), "ghost")

    _assert_learned_only_in_ghost()


@pytest.mark.asyncio
async def test_import_url_in_ghost_learns_only_in_ghost(db_session, monkeypatch):
    db_session._workspace = "ghost"
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch())

    await scrape_router.import_from_url(scrape_router.ImportURLRequest(url=CH1_URL), db=db_session)

    _assert_learned_only_in_ghost()


@pytest.mark.asyncio
async def test_fetch_next_in_ghost_learns_only_in_ghost(db_session, monkeypatch):
    thread, chapter = _seed(db_session, workspace="ghost")
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch())

    await scrape_router.fetch_next_chapter(thread.id, chapter.id, db=db_session)

    _assert_learned_only_in_ghost()


@pytest.mark.asyncio
async def test_crawl_next_in_ghost_learns_only_in_ghost(db_session, monkeypatch):
    thread, chapter = _seed(db_session, workspace="ghost")
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch())
    monkeypatch.setattr(scrape_router, "SessionLocal", lambda workspace=None: db_session)
    request = Request({"type": "http", "headers": [(b"x-workspace", b"ghost"), (b"cookie", f"{__import__('database').GHOST_SESSION_COOKIE}={__import__('database').issue_ghost_session()}".encode())]})

    response = await scrape_router.crawl_next_chapters(
        thread.id, scrape_router.CrawlNextChaptersRequest(start_chapter_id=chapter.id, count=1), request
    )
    async for _ in response.body_iterator:
        pass

    _assert_learned_only_in_ghost()


@pytest.mark.asyncio
async def test_fetch_html_adaptive_spa_probe_learns_in_callers_workspace(monkeypatch):
    spa_shell = f"<html><body><div id='app'></div><h1>第一章</h1><div id='content'>{_PROSE}</div></body></html>"

    class _Resp:
        status_code = 200
        url = CH1_URL
        headers = {"content-type": "text/html; charset=utf-8"}
        content = spa_shell.encode("utf-8")
        text = spa_shell
        encoding = "utf-8"

        def raise_for_status(self):
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            return _Resp()

    monkeypatch.setattr(scrape_router, "create_safe_async_client", lambda **kwargs: _Client())

    await scrape_router.fetch_html_adaptive(CH1_URL, workspace="ghost", allow_playwright_fallback=False)

    _assert_learned_only_in_ghost()


@pytest.mark.asyncio
async def test_on_demand_scrape_in_ghost_learns_only_in_ghost(db_session, monkeypatch):
    _, chapter = _seed(db_session, workspace="ghost")
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch())

    assert await threads_router._scrape_chapter_on_demand(db_session, chapter, "ghost") is True

    _assert_learned_only_in_ghost()


def test_novalpie_parser_learns_in_adapter_workspace():
    from services.scrapers.novalpie import NovalpieAdapter

    html = (
        "<html><body><div id='chapter-101'><h2>第1章 觉醒</h2>"
        f"{_PROSE}</div></body></html>"
    )
    NovalpieAdapter(workspace="ghost")._parse_chapter_html(html, chapter_id=101)

    assert _domain_keys(_main_store(), "novalpie.cc") == set()
    assert {"novalpie.cc::chapter_content", "novalpie.cc::chapter_title"} <= _disk_keys(_ghost_store())


def test_stealth_extract_clean_chapter_learns_in_given_workspace():
    from services.scrapers.stealth_base import StealthyNovelAdapter

    StealthyNovelAdapter.extract_clean_chapter(
        _chapter_html("第一章"), "h1", "#content", auto_save=True, domain=DOMAIN, workspace="ghost"
    )

    _assert_learned_only_in_ghost()


def test_stealth_playwright_page_carries_adapter_workspace(monkeypatch):
    from services.scrapers import stealth_base

    class _Page:
        url = CH1_URL

        def goto(self, *args, **kwargs):
            return type("R", (), {"status": 200, "headers": {}})()

        def wait_for_timeout(self, ms):
            return None

    class _Entry:
        context = type("C", (), {"new_page": lambda self: _Page(), "add_cookies": lambda self, c: None})()
        proxy_verified = True

    proxy = type("P", (), {"server_url": "http://127.0.0.1:1", "handled": 0, "blocked": 0})()
    monkeypatch.setattr(stealth_base, "_get_thread_launcher", lambda: object())
    monkeypatch.setattr(stealth_base, "get_egress_proxy", lambda: proxy)
    monkeypatch.setattr(stealth_base, "_acquire_context", lambda browser, key, url: _Entry())
    monkeypatch.setattr(stealth_base, "_release_context", lambda key, entry, keep: None)
    monkeypatch.setattr(stealth_base, "_install_ssrf_guard", lambda context, page: {"blocked_document": False})
    monkeypatch.setattr(stealth_base, "apply_client_hints", lambda *a: None)
    monkeypatch.setattr(stealth_base, "_install_resource_shield", lambda *a, **k: None)
    monkeypatch.setattr(stealth_base, "cloudflare_poll_step", lambda *a, **k: False)
    monkeypatch.setattr(stealth_base, "_page_content", lambda page: _chapter_html("第一章"))

    adapter = stealth_base.StealthyNovelAdapter(workspace="ghost", adaptive_domain=CH1_URL)
    page = adapter._fetch_playwright_sync(CH1_URL, disable_resources=False)
    page.css("#content", auto_save=True)

    _assert_learned_only_in_ghost()


@pytest.mark.asyncio
async def test_ghost_split_chapter_subpages_learn_only_in_ghost(monkeypatch):
    # Issue 26 follow-up: the sub-page parse dropped the workspace, so it fell back to the
    # process-wide default (main) and wrote a ghost site's selectors to the main store.
    import database

    monkeypatch.setattr(database, "ACTIVE_WORKSPACE", "main")
    first_url = f"https://{DOMAIN}/book/1/101.html"
    sub_url = f"https://{DOMAIN}/book/1/101_2.html"
    first_html = (
        f"<html><body><h1>第一章</h1><div id='content'>{_PROSE}</div>"
        "<a href='101_2.html'>下一页</a></body></html>"
    )
    monkeypatch.setattr(
        scrape_router, "fetch_html_adaptive", _fake_fetch({sub_url: (_chapter_html("第一章"), sub_url)})
    )

    await scrape_router.stitch_subpages_markdown(first_html, first_url, "第一页", workspace="ghost")

    _assert_learned_only_in_ghost()
