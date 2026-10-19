"""
Generic (non-dedicated) site quality: SPA shell detection, chapter-title picking,
pirate-site watermark removal, and not mislabelling failed extraction as a VIP chapter.
"""

import json
import time
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import routers.scrape as scrape_router
import routers.threads as threads_router
from database import Chapter, Thread
from routers.scrape import _SPA_SHELL_RE, html_to_markdown
from services.scrapers.generic_cleanup import clean_title_tag_text, is_vip_chapter, strip_watermarks

_PROSE = "".join(
    f"<p>这是第{i}段正文，主角走进了房间。他看着窗外，心里想着明天的事情。</p>" for i in range(8)
)
URL = "https://generic-novel.example/book/1/1.html"


# --- SPA shell detection ------------------------------------------------------------------

@pytest.mark.parametrize(
    "html",
    [
        '<div id="app"></div>',
        '<div id="__nuxt">  </div>',
        "<script>window.__NUXT__={}</script>",
        '<script id="__NEXT_DATA__" type="application/json">{}</script>',
    ],
    ids=["empty-app-mount", "empty-nuxt-mount", "nuxt-state", "next-data"],
)
def test_spa_shell_regex_detects_client_rendered_shells(html):
    assert _SPA_SHELL_RE.search(html)


def test_spa_shell_regex_ignores_server_rendered_app_div():
    assert not _SPA_SHELL_RE.search(f'<div id="app">{_PROSE}</div>')


# --- chapter title ------------------------------------------------------------------------

def test_title_prefers_chapter_heading_over_site_logo_h1():
    html = (
        "<html><body><h1 class='logo'>某站小说网</h1><h3 class='chapter'>第五章 夜雨</h3>"
        f"<div class='read'>{_PROSE}</div></body></html>"
    )

    title, _ = html_to_markdown(html, url=URL)

    assert title == "第五章 夜雨"


def test_title_prefers_chapter_numbered_heading_over_plain_site_name_h1():
    html = (
        "<html><body><h1>站点名</h1>"
        f"<div id='chaptercontent'><h2>第十章 风起</h2>{_PROSE}</div></body></html>"
    )

    title, _ = html_to_markdown(html, url=URL)

    assert title == "第十章 风起"


def test_title_recognises_english_chapter_heading():
    html = (
        "<html><body><h1>My Novel Site</h1><h2>Chapter 12: The Return</h2>"
        f"<div class='chapter-content'>{_PROSE}</div></body></html>"
    )

    title, _ = html_to_markdown(html, url=URL)

    assert title == "Chapter 12: The Return"


@pytest.mark.parametrize(
    "page_title",
    ["第五章 夜雨_某书_某站", "第五章 夜雨 - 某书 - 某站", "第五章 夜雨 | 某站"],
)
def test_title_tag_fallback_drops_site_and_book_suffix(page_title):
    html = f"<html><head><title>{page_title}</title></head><body><div class='read'>{_PROSE}</div></body></html>"

    title, _ = html_to_markdown(html, url=URL)

    assert title == "第五章 夜雨"


# --- watermark removal --------------------------------------------------------------------

def test_watermark_line_between_paragraphs_is_removed():
    html = (
        f"<html><body><h1>第三章</h1><div id='content'>{_PROSE}"
        "<br><br>请记住本书首发域名：www.xxbiquge.com。笔趣阁手机版阅读网址：m.xxbiquge.com<br><br>"
        f"{_PROSE}</div></body></html>"
    )

    _, markdown = html_to_markdown(html, url=URL)

    assert "主角走进了房间" in markdown
    assert "首发域名" not in markdown
    assert "xxbiquge" not in markdown


def test_watermark_sentence_inside_paragraph_is_removed_and_prose_kept():
    html = (
        "<html><body><h1>第三章</h1><div id='content'>"
        "<p>他推开门走了进去。天才一秒记住本站地址：www.biqu.cc。屋里一片漆黑，什么也看不见。</p>"
        f"{_PROSE}</div></body></html>"
    )

    _, markdown = html_to_markdown(html, url=URL)

    assert "他推开门走了进去。" in markdown
    assert "屋里一片漆黑，什么也看不见。" in markdown
    assert "一秒记住" not in markdown


def test_english_watermark_line_is_removed():
    html = (
        "<html><body><h1>Chapter 1</h1><div class='chapter-content'>"
        "<p>He walked into the room and looked out of the window for a long while.</p>"
        "<p>This chapter upload first at NovelBin.Com</p>"
        "<p>Tomorrow would be different, he thought, as the rain kept falling outside.</p>"
        "</div></body></html>"
    )

    _, markdown = html_to_markdown(html, url=URL)

    assert "He walked into the room" in markdown
    assert "Tomorrow would be different" in markdown
    assert "NovelBin" not in markdown


def test_prose_using_watermark_like_words_is_kept():
    html = (
        "<html><body><h1>第三章</h1><div id='content'>"
        "<p>“请记住这一天，”她说，“我们会再见面的。”</p>"
        f"{_PROSE}</div></body></html>"
    )

    _, markdown = html_to_markdown(html, url=URL)

    assert "请记住这一天" in markdown


@pytest.mark.parametrize(
    "prose",
    [
        "林凡看着眼前的笔趣阁，心中感慨万千。",
        "“最快更新的消息是什么？”他问道。",
        "他把书加入书签后便睡了。窗外下着雨。",
        "Mr. Smith read the latest chapters on the train. It was late.",
    ],
)
def test_strip_watermarks_keeps_prose_that_only_mentions_watermark_words(prose):
    assert strip_watermarks(prose) == prose


def test_strip_watermarks_removes_only_the_glued_watermark_span():
    assert strip_watermarks("他转身离开了房间一秒记住【xxx.com】，精彩无弹窗免费阅读！") == "他转身离开了房间"


def test_clean_title_tag_text_stays_linear_on_huge_whitespace_title():
    started = time.perf_counter()

    clean_title_tag_text("某书" + " " * 20_000 + "夜雨")

    assert time.perf_counter() - started < 0.5


# --- VIP detection only trusts explicit lock notices --------------------------------------

@pytest.mark.parametrize(
    "markdown",
    ["作者有话说：感谢大家订阅本章！明天两更。", "“这是VIP章节吗？”他问。"],
    ids=["author-note", "dialogue"],
)
def test_short_chapter_mentioning_subscription_is_not_vip(markdown):
    assert not is_vip_chapter("https://generic-novel.example/1", "第3章", markdown)


def test_dedicated_source_content_is_never_inspected_for_vip_notice():
    notice = "该章节为VIP章节，请订阅后阅读。"

    assert is_vip_chapter("https://generic-novel.example/1", "第3章", notice)
    assert not is_vip_chapter("https://book.sfacg.com/1", "第3章", notice, inspect_content=False)


# --- failed extraction is not a VIP chapter -----------------------------------------------

CH1_URL = "https://generic-novel.example/book/1/1.html"
CH2_URL = "https://generic-novel.example/book/1/2.html"
EMPTY_PAGE = "<html><body><div id='app'></div></body></html>"
LOCKED_PAGE = "<html><body><h1>第二章</h1><div id='content'>该章节为VIP章节，请订阅后阅读。</div></body></html>"


def _ch1_html() -> str:
    return f"<html><body><h1>第一章</h1><div id='content'>{_PROSE}</div><a href='/book/1/2.html'>下一章</a></body></html>"


def _fake_fetch(ch2_html: str):
    pages = {CH1_URL: (_ch1_html(), CH1_URL), CH2_URL: (ch2_html, CH2_URL)}

    async def fetch(url, *, workspace=None, allow_playwright_fallback=True):
        return pages[url]

    return AsyncMock(side_effect=fetch)


def _seed(db):
    db._workspace = "main"
    thread = Thread(title="Generic Novel", source_url=CH1_URL)
    db.add(thread)
    db.commit()
    chapter = Chapter(thread_id=thread.id, order=1, title_original="第一章", content_original="x", source_url=CH1_URL)
    db.add(chapter)
    db.commit()
    return thread, chapter


async def _drain(response) -> list[dict]:
    events = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        payload = text.removeprefix("data: ").strip()
        if payload and payload != "[DONE]":
            events.append(json.loads(payload))
    return events


@pytest.mark.asyncio
async def test_fetch_next_with_empty_extraction_raises_instead_of_saving_vip(db_session, monkeypatch):
    thread, chapter = _seed(db_session)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch(EMPTY_PAGE))

    with pytest.raises(HTTPException) as exc_info:
        await scrape_router.fetch_next_chapter(thread.id, chapter.id, db=db_session)

    assert exc_info.value.status_code == 422
    assert db_session.query(Chapter).filter(Chapter.source_url == CH2_URL).count() == 0


@pytest.mark.asyncio
async def test_fetch_next_with_locked_notice_still_saves_vip(db_session, monkeypatch):
    thread, chapter = _seed(db_session)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch(LOCKED_PAGE))

    result = await scrape_router.fetch_next_chapter(thread.id, chapter.id, db=db_session)

    assert db_session.get(Chapter, result["chapter_id"]).translation_status == "vip"


@pytest.mark.asyncio
async def test_crawl_next_stops_with_extraction_failed_instead_of_vip(db_session, monkeypatch):
    thread, chapter = _seed(db_session)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch(EMPTY_PAGE))
    monkeypatch.setattr(scrape_router, "SessionLocal", lambda workspace=None: db_session)
    monkeypatch.setattr(scrape_router.asyncio, "sleep", AsyncMock())
    request = Request({"type": "http", "headers": []})

    response = await scrape_router.crawl_next_chapters(
        thread.id, scrape_router.CrawlNextChaptersRequest(start_chapter_id=chapter.id, count=3), request
    )
    events = await _drain(response)

    complete = [e for e in events if e["type"] == "complete"]
    assert [e["reason"] for e in complete] == ["extraction_failed"], events
    assert db_session.query(Chapter).filter(Chapter.source_url == CH2_URL).count() == 0


@pytest.mark.asyncio
async def test_import_url_with_empty_extraction_raises_instead_of_saving_vip(db_session, monkeypatch):
    db_session._workspace = "main"
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch(EMPTY_PAGE))

    with pytest.raises(HTTPException) as exc_info:
        await scrape_router.import_from_url(scrape_router.ImportURLRequest(url=CH2_URL), db=db_session)

    assert exc_info.value.status_code == 422
    assert db_session.query(Chapter).count() == 0


@pytest.mark.asyncio
async def test_on_demand_read_with_empty_extraction_leaves_chapter_unfetched(db_session, monkeypatch):
    thread, _ = _seed(db_session)
    pending = Chapter(thread_id=thread.id, order=2, title_original=None, content_original=None, source_url=CH2_URL)
    db_session.add(pending)
    db_session.commit()
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fake_fetch(EMPTY_PAGE))

    await threads_router._scrape_chapter_on_demand(db_session, pending, "main")

    db_session.refresh(pending)
    assert pending.translation_status != "vip"
    assert pending.content_original is None
