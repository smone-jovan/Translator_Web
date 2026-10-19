"""
On-demand chapter scrapes (GET /threads/{id}/chapters/{id} and N±1 warming) back off after a
failure: a chapter whose fetch came back empty or raised is not re-fetched for a cooldown window,
per (workspace, chapter). A success clears the entry; ghost and main never share entries.
"""

from unittest.mock import AsyncMock

import pytest

import routers.scrape as scrape_router
import routers.threads as threads_router
from database import Chapter, Thread, make_workspace_key

_PROSE = "".join(
    f"<p>这是第{i}段正文，主角走进了房间。他看着窗外，心里想着明天的事情。</p>" for i in range(8)
)
CH1_URL = "https://generic-novel.example/book/1/1.html"
CH2_URL = "https://generic-novel.example/book/1/2.html"
EMPTY_PAGE = "<html><body><div id='app'></div></body></html>"
GOOD_PAGE = f"<html><body><h1>第二章</h1><div id='content'>{_PROSE}</div></body></html>"


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(threads_router, "_cooldown_clock", fake)
    monkeypatch.setattr(threads_router, "_failed_chapter_scrapes", {})
    monkeypatch.setattr(threads_router, "_inflight_chapter_scrapes", {})
    return fake


def _fetch_returning(*pages: str) -> AsyncMock:
    """Each await returns the next page; the last page repeats."""
    queue = list(pages)

    async def fetch(url, *, workspace=None, allow_playwright_fallback=True):
        html = queue.pop(0) if len(queue) > 1 else queue[0]
        return html, url

    return AsyncMock(side_effect=fetch)


def _seed_pending(db, *, count: int = 1) -> list[Chapter]:
    db._workspace = "main"
    thread = Thread(title="Generic Novel", source_url=CH1_URL)
    db.add(thread)
    db.commit()
    pending = [
        Chapter(thread_id=thread.id, order=i + 2, title_original=None, content_original=None,
                source_url=f"https://generic-novel.example/book/1/{i + 2}.html")
        for i in range(count)
    ]
    db.add_all(pending)
    db.commit()
    return pending


@pytest.mark.asyncio
async def test_failed_scrape_then_immediate_retry_does_not_fetch_again(db_session, monkeypatch):
    (chapter,) = _seed_pending(db_session)
    fetch = _fetch_returning(EMPTY_PAGE)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fetch)

    await threads_router._scrape_chapter_once(db_session, chapter, "main")
    await threads_router._scrape_chapter_once(db_session, chapter, "main")

    assert fetch.await_count == 1
    db_session.refresh(chapter)
    assert chapter.content_original is None


@pytest.mark.asyncio
async def test_raised_fetch_error_also_starts_cooldown(db_session, monkeypatch):
    (chapter,) = _seed_pending(db_session)
    fetch = AsyncMock(side_effect=RuntimeError("cloudflare challenge timed out"))
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fetch)

    await threads_router._scrape_chapter_once(db_session, chapter, "main")
    await threads_router._scrape_chapter_once(db_session, chapter, "main")

    assert fetch.await_count == 1


@pytest.mark.asyncio
async def test_after_cooldown_elapses_scrape_fetches_again(db_session, monkeypatch, clock):
    (chapter,) = _seed_pending(db_session)
    fetch = _fetch_returning(EMPTY_PAGE, GOOD_PAGE)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fetch)

    await threads_router._scrape_chapter_once(db_session, chapter, "main")
    clock.now += threads_router.ON_DEMAND_SCRAPE_FAILURE_COOLDOWN_SECONDS - 1
    await threads_router._scrape_chapter_once(db_session, chapter, "main")
    assert fetch.await_count == 1

    clock.now += 2
    await threads_router._scrape_chapter_once(db_session, chapter, "main")

    assert fetch.await_count == 2
    db_session.refresh(chapter)
    assert "主角走进了房间" in chapter.content_original


@pytest.mark.asyncio
async def test_successful_scrape_clears_cooldown_entry(db_session, monkeypatch, clock):
    (chapter,) = _seed_pending(db_session)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fetch_returning(EMPTY_PAGE, GOOD_PAGE))
    key = make_workspace_key("main", chapter.id)

    await threads_router._scrape_chapter_once(db_session, chapter, "main")
    assert key in threads_router._failed_chapter_scrapes

    clock.now += threads_router.ON_DEMAND_SCRAPE_FAILURE_COOLDOWN_SECONDS + 1
    await threads_router._scrape_chapter_once(db_session, chapter, "main")

    assert key not in threads_router._failed_chapter_scrapes


@pytest.mark.asyncio
async def test_cooldown_in_main_does_not_block_same_chapter_id_in_ghost(db_session, monkeypatch):
    (chapter,) = _seed_pending(db_session)
    fetch = _fetch_returning(EMPTY_PAGE)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fetch)

    await threads_router._scrape_chapter_once(db_session, chapter, "main")
    await threads_router._scrape_chapter_once(db_session, chapter, "ghost")

    assert fetch.await_count == 2
    assert [c.kwargs.get("workspace") for c in fetch.await_args_list] == ["main", "ghost"]
    assert make_workspace_key("ghost", chapter.id) in threads_router._failed_chapter_scrapes
    assert make_workspace_key("main", chapter.id) in threads_router._failed_chapter_scrapes


@pytest.mark.asyncio
async def test_cooldown_registry_is_bounded(db_session, monkeypatch, clock):
    monkeypatch.setattr(threads_router, "ON_DEMAND_SCRAPE_FAILURE_MAX_ENTRIES", 3)
    chapters = _seed_pending(db_session, count=5)
    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", _fetch_returning(EMPTY_PAGE))

    for chapter in chapters:
        clock.now += 1
        await threads_router._scrape_chapter_once(db_session, chapter, "main")

    registry = threads_router._failed_chapter_scrapes
    assert len(registry) == 3
    # The oldest failures are evicted first; the newest are kept.
    assert set(registry) == {make_workspace_key("main", c.id) for c in chapters[-3:]}
