"""
GET /threads/{id}/chapters/{chapter_id} men-scrape on-demand bab yang belum punya content_original.
Request konkuren untuk bab yang sama (dua tab/perangkat, warming N±1 ?track=0, offline cache)
harus berbagi satu scrape: request kedua menunggu hasil scrape pertama lalu membaca ulang bab
dari session DB-nya sendiri. Entry in-flight dibersihkan setelah selesai, termasuk saat gagal.
"""
import asyncio
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, Chapter, Thread, get_db
from main import app

SOURCE_URL = "https://novalpie.cc/viewer/123/456"
SCRAPED_CONTENT = "Isi bab hasil scrape on-demand. " * 5


def _make_factory(path):
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def factories(tmp_path):
    """One file-backed database per workspace, like app.db / ghost.db."""
    engines, result = [], {}
    for ws in ("main", "ghost"):
        engine, factory = _make_factory(tmp_path / f"{ws}.db")
        engines.append(engine)
        result[ws] = factory
    yield result
    for engine in engines:
        engine.dispose()


@pytest.fixture
def opened_sessions(factories):
    """Every request gets its own Session for its X-Workspace, as with the real get_db."""
    opened = []

    def override_get_db(request: Request):
        ws = request.headers.get("X-Workspace", "main")
        db = factories[ws]()
        db._workspace = ws
        opened.append(db)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield opened
    app.dependency_overrides.clear()


def _seed_unscraped_chapter(factory):
    with factory() as db:
        thread = Thread(title="Dedupe", source_type="novalpie")
        db.add(thread)
        db.commit()
        chapter = Chapter(thread_id=thread.id, order=1, source_url=SOURCE_URL)
        db.add(chapter)
        db.commit()
        return f"/api/threads/{thread.id}/chapters/{chapter.id}"


def _fake_adapter(release, calls, fail_first=False, first_error=None):
    class FakeNovalpieAdapter:
        def __init__(self, workspace=None):
            self.workspace = workspace

        async def scrape_chapter_content(self, url):
            call_index = len(calls)
            calls.append((self.workspace, url))
            await release.wait()
            if call_index == 0 and first_error is not None:
                raise first_error
            if fail_first and call_index == 0:
                raise RuntimeError("scrape gagal")
            return "Judul Bab", SCRAPED_CONTENT

    return FakeNovalpieAdapter


async def _wait_for(predicate, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            return False
        await asyncio.sleep(0.005)
    return True


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _two_overlapping_reads(client, calls, opened, release, first, second):
    """Start `first`, then `second` while the first scrape is still blocked, then release."""
    first_task = asyncio.create_task(first())
    assert await _wait_for(lambda: len(calls) == 1), "first request never started scraping"
    second_task = asyncio.create_task(second())
    assert await _wait_for(lambda: len(opened) == 2), "second request never reached the handler"
    # Give a non-deduplicated second request the chance to start its own scrape.
    await _wait_for(lambda: len(calls) > 1, timeout=0.2)
    release.set()
    return await asyncio.gather(first_task, second_task)


@pytest.mark.asyncio
async def test_concurrent_reads_of_same_chapter_share_one_scrape(factories, opened_sessions):
    url = _seed_unscraped_chapter(factories["main"])
    release, calls = asyncio.Event(), []

    with patch("services.scrapers.novalpie.NovalpieAdapter", _fake_adapter(release, calls)):
        async with _client() as client:
            r1, r2 = await _two_overlapping_reads(
                client, calls, opened_sessions, release,
                lambda: client.get(url),
                lambda: client.get(url, params={"track": 0}),
            )

    assert len(calls) == 1
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["content_original"] == SCRAPED_CONTENT
    assert r2.json()["content_original"] == SCRAPED_CONTENT
    assert r2.json()["title_original"] == "Judul Bab"
    assert len({id(s) for s in opened_sessions}) == 2


@pytest.mark.asyncio
async def test_failed_scrape_is_shared_then_cleared_so_next_read_retries(factories, opened_sessions):
    url = _seed_unscraped_chapter(factories["main"])
    release, calls = asyncio.Event(), []

    with patch("services.scrapers.novalpie.NovalpieAdapter", _fake_adapter(release, calls, fail_first=True)):
        async with _client() as client:
            r1, r2 = await _two_overlapping_reads(
                client, calls, opened_sessions, release,
                lambda: client.get(url),
                lambda: client.get(url, params={"track": 0}),
            )
            # The waiter shared the failed attempt instead of starting a second scrape.
            assert len(calls) == 1
            assert r1.status_code == 200 and r2.status_code == 200
            assert not r1.json()["content_original"]
            assert not r2.json()["content_original"]

            retry = await client.get(url)

    assert len(calls) == 2
    assert retry.status_code == 200
    assert retry.json()["content_original"] == SCRAPED_CONTENT


@pytest.mark.asyncio
async def test_rejected_scrape_returns_same_error_to_waiter_then_clears(factories, opened_sessions):
    url = _seed_unscraped_chapter(factories["main"])
    release, calls = asyncio.Event(), []
    blocked = HTTPException(status_code=400, detail="Redirect ke host terlarang")

    with patch("services.scrapers.novalpie.NovalpieAdapter", _fake_adapter(release, calls, first_error=blocked)):
        async with _client() as client:
            r1, r2 = await _two_overlapping_reads(
                client, calls, opened_sessions, release,
                lambda: client.get(url),
                lambda: client.get(url, params={"track": 0}),
            )
            assert len(calls) == 1
            assert r1.status_code == 400 and r2.status_code == 400
            assert r2.json()["detail"] == "Redirect ke host terlarang"

            retry = await client.get(url)

    assert len(calls) == 2
    assert retry.json()["content_original"] == SCRAPED_CONTENT


@pytest.mark.asyncio
async def test_same_chapter_id_in_other_workspace_is_not_deduplicated(factories, opened_sessions):
    main_url = _seed_unscraped_chapter(factories["main"])
    ghost_url = _seed_unscraped_chapter(factories["ghost"])
    assert main_url == ghost_url  # same raw chapter id in both databases
    release, calls = asyncio.Event(), []

    with patch("services.scrapers.novalpie.NovalpieAdapter", _fake_adapter(release, calls)):
        async with _client() as client:
            first_task = asyncio.create_task(client.get(main_url, headers={"X-Workspace": "main"}))
            assert await _wait_for(lambda: len(calls) == 1)
            second_task = asyncio.create_task(client.get(ghost_url, headers={"X-Workspace": "ghost"}))
            assert await _wait_for(lambda: len(calls) == 2), "ghost read waited on main's scrape"
            release.set()
            r_main, r_ghost = await asyncio.gather(first_task, second_task)

    assert sorted(ws for ws, _ in calls) == ["ghost", "main"]
    assert r_main.json()["content_original"] == SCRAPED_CONTENT
    assert r_ghost.json()["content_original"] == SCRAPED_CONTENT
