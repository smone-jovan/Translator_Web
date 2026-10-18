"""
Generic (non-novalpie, non-sfacg) next-chapter paths must fetch through fetch_html_adaptive
(Cloudflare/403/SPA escalation) with the caller's workspace, not plain httpx with a bot UA.
Covers fetch-next, crawl-next and the on-demand scrape in GET /threads/{id}/chapters/{id}.
"""

import json
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

import routers.scrape as scrape_router
import routers.threads as threads_router
from database import Chapter, Thread

_PROSE = "".join(
    f"<p>这是第{i}段正文，主角走进了房间。他看着窗外，心里想着明天的事情。</p>" for i in range(8)
)
CH1_URL = "https://generic-novel.example/book/1/1.html"
CH1_FINAL_URL = "https://www.generic-novel.example/book/1/1.html"
CH2_URL = "https://www.generic-novel.example/book/1/2.html"


def _chapter_html(title: str, next_href: str | None) -> str:
    nav = f"<a href='{next_href}'>下一章</a>" if next_href else ""
    return f"<html><body><h1>{title}</h1><div id='content'>{_PROSE}</div>{nav}</body></html>"


PAGES = {
    CH1_URL: (_chapter_html("第一章", "/book/1/2.html"), CH1_FINAL_URL),
    CH2_URL: (_chapter_html("第二章 新的开始", None), CH2_URL),
}


def _fake_fetch(pages=PAGES):
    async def fetch(url, *, workspace=None, allow_playwright_fallback=True):
        return pages[url]

    return AsyncMock(side_effect=fetch)


@pytest.fixture
def plain_httpx_forbidden(monkeypatch):
    """Any direct create_safe_async_client use from the routers is the bug under test."""
    def boom(*args, **kwargs):
        raise AssertionError("generic path must use fetch_html_adaptive, not plain httpx")

    monkeypatch.setattr(scrape_router, "create_safe_async_client", boom)
    monkeypatch.setattr("services.security.create_safe_async_client", boom)


def _seed(db, *, workspace: str):
    db._workspace = workspace
    thread = Thread(title="Generic Novel", source_url=CH1_URL)
    db.add(thread)
    db.commit()
    chapter = Chapter(thread_id=thread.id, order=1, title_original="第一章", content_original="x", source_url=CH1_URL)
    db.add(chapter)
    db.commit()
    return thread, chapter


@pytest.mark.asyncio
async def test_fetch_next_uses_adaptive_fetch_with_workspace(db_session, monkeypatch, plain_httpx_forbidden):
    thread, chapter = _seed(db_session, workspace="ghost")
    fetch = _fake_fetch()
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fetch)
    markdown_urls = []
    real_html_to_markdown = scrape_router.html_to_markdown

    def spy_html_to_markdown(html, url=""):
        markdown_urls.append(url)
        return real_html_to_markdown(html, url=url)

    monkeypatch.setattr(scrape_router, "html_to_markdown", spy_html_to_markdown)

    result = await scrape_router.fetch_next_chapter(thread.id, chapter.id, db=db_session)

    assert [c.args[0] for c in fetch.await_args_list] == [CH1_URL, CH2_URL]
    assert all(c.kwargs.get("workspace") == "ghost" for c in fetch.await_args_list)
    new_chapter = db_session.get(Chapter, result["chapter_id"])
    # Relative next link resolved against the post-redirect URL of the current chapter.
    assert new_chapter.source_url == CH2_URL
    assert new_chapter.title_original == "第二章 新的开始"
    assert "主角走进了房间" in new_chapter.content_original
    assert markdown_urls == [CH2_URL]


async def _drain(response) -> list[dict]:
    events = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        payload = text.removeprefix("data: ").strip()
        if payload and payload != "[DONE]":
            events.append(json.loads(payload))
    return events


@pytest.mark.asyncio
async def test_crawl_next_uses_adaptive_fetch_with_request_workspace(db_session, monkeypatch, plain_httpx_forbidden):
    thread, chapter = _seed(db_session, workspace="ghost")
    fetch = _fake_fetch()
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fetch)
    monkeypatch.setattr(scrape_router, "SessionLocal", lambda workspace=None: db_session)
    request = Request({"type": "http", "headers": [(b"x-workspace", b"ghost")]})

    response = await scrape_router.crawl_next_chapters(
        thread.id, scrape_router.CrawlNextChaptersRequest(start_chapter_id=chapter.id, count=1), request
    )
    events = await _drain(response)

    assert [e["type"] for e in events if e["type"] in ("error", "complete")] == ["complete"], events
    assert [c.args[0] for c in fetch.await_args_list] == [CH1_URL, CH2_URL]
    assert all(c.kwargs.get("workspace") == "ghost" for c in fetch.await_args_list)
    created = db_session.query(Chapter).filter(Chapter.source_url == CH2_URL).one()
    assert "主角走进了房间" in created.content_original
    assert created.translation_status == "idle"


@pytest.mark.asyncio
async def test_crawl_next_retries_adaptive_fetch_of_next_chapter(db_session, monkeypatch, plain_httpx_forbidden):
    thread, chapter = _seed(db_session, workspace="main")
    calls = {"ch2": 0}

    async def flaky(url, *, workspace=None, allow_playwright_fallback=True):
        if url == CH2_URL:
            calls["ch2"] += 1
            if calls["ch2"] == 1:
                raise RuntimeError("transient 503")
        return PAGES[url]

    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", AsyncMock(side_effect=flaky))
    monkeypatch.setattr(scrape_router, "SessionLocal", lambda workspace=None: db_session)
    monkeypatch.setattr(scrape_router.asyncio, "sleep", AsyncMock())
    request = Request({"type": "http", "headers": []})

    response = await scrape_router.crawl_next_chapters(
        thread.id, scrape_router.CrawlNextChaptersRequest(start_chapter_id=chapter.id, count=1), request
    )
    await _drain(response)

    assert calls["ch2"] == 2
    created = db_session.query(Chapter).filter(Chapter.source_url == CH2_URL).one()
    assert created.translation_status == "idle"


@pytest.mark.asyncio
async def test_on_demand_read_uses_adaptive_fetch_with_workspace(db_session, monkeypatch, plain_httpx_forbidden):
    thread, _ = _seed(db_session, workspace="ghost")
    empty = Chapter(thread_id=thread.id, order=2, title_original=None, content_original=None, source_url=CH2_URL)
    db_session.add(empty)
    db_session.commit()
    fetch = _fake_fetch()
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fetch)

    await threads_router._scrape_chapter_on_demand(db_session, empty, "ghost")

    assert [c.args[0] for c in fetch.await_args_list] == [CH2_URL]
    assert fetch.await_args_list[0].kwargs.get("workspace") == "ghost"
    db_session.refresh(empty)
    assert "主角走进了房间" in empty.content_original
    assert empty.title_original == "第二章 新的开始"


@pytest.mark.asyncio
async def test_fetch_next_skips_next_volume_link(db_session, monkeypatch, plain_httpx_forbidden):
    thread, chapter = _seed(db_session, workspace="main")
    ch1_html = (
        f"<html><body><h1>第一章</h1><div id='content'>{_PROSE}</div>"
        "<a href='/book/2/1.html'>下一卷</a><a href='/book/1/2.html'>下一章</a></body></html>"
    )
    pages = {**PAGES, CH1_URL: (ch1_html, CH1_FINAL_URL)}
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch(pages))

    result = await scrape_router.fetch_next_chapter(thread.id, chapter.id, db=db_session)

    assert db_session.get(Chapter, result["chapter_id"]).source_url == CH2_URL
