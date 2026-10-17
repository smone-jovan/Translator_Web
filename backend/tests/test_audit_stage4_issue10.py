import inspect
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException


def test_translation_queues_strictly_workspace_scoped():
    """get_chapter_translation_queues and translate.py must not register or fallback to integer chapter_id."""
    from services.background_translator import get_chapter_translation_queues, translation_queues
    import routers.translate as translate_router

    # Verify get_chapter_translation_queues definition
    source_getter = inspect.getsource(get_chapter_translation_queues)
    assert "translation_queues.get(chapter_id)" not in source_getter, (
        "get_chapter_translation_queues must not fallback to integer chapter_id"
    )

    # Verify translate.py sse_wrapper
    source_translate = inspect.getsource(translate_router.translate_stream)
    assert "translation_queues[req.chapter_id]" not in source_translate, (
        "translate_stream must not assign queues to integer chapter_id"
    )


def test_novalpie_router_instantiations_pass_workspace():
    """Routers (scrape.py, toc.py, threads.py) and background_translator.py must pass workspace to NovalpieAdapter."""
    import routers.scrape as scrape_router
    import routers.toc as toc_router
    import routers.threads as threads_router

    source_scrape = inspect.getsource(scrape_router)
    source_toc = inspect.getsource(toc_router)
    source_threads = inspect.getsource(threads_router.get_chapter)

    # In scrape.py, import_from_url and fetch_next_chapter should pass workspace
    assert "NovalpieAdapter(workspace=" in source_scrape, "scrape.py must pass workspace to NovalpieAdapter"
    assert "NovalpieAdapter(workspace=" in source_toc, "toc.py must pass workspace to NovalpieAdapter"
    assert "NovalpieAdapter(workspace=" in source_threads, "threads.py must pass workspace to NovalpieAdapter"


def test_novalpie_scrape_metadata_and_toc_use_safe_client():
    """NovalpieAdapter.scrape_metadata and scrape_toc must use create_safe_async_client to prevent SSRF redirects."""
    from services.scrapers.novalpie import NovalpieAdapter
    source_meta = inspect.getsource(NovalpieAdapter.scrape_metadata)
    source_toc = inspect.getsource(NovalpieAdapter.scrape_toc)

    assert "create_safe_async_client" in source_meta, "NovalpieAdapter.scrape_metadata must use create_safe_async_client"
    assert "create_safe_async_client" in source_toc, "NovalpieAdapter.scrape_toc must use create_safe_async_client"


def test_sfacg_and_novalpie_toc_root_url_pattern():
    """TOC_ROOT_URL_PATTERN in scrape.py must reject novel TOC URLs for both Novalpie and SFACG."""
    import routers.scrape as scrape_router
    assert hasattr(scrape_router, "TOC_ROOT_URL_PATTERN"), "scrape.py must define TOC_ROOT_URL_PATTERN"
    pattern = getattr(scrape_router, "TOC_ROOT_URL_PATTERN")

    assert pattern.match("https://novalpie.cc/book/12345")
    assert pattern.match("https://novalpie.cc/novel/12345/")
    assert pattern.match("https://book.sfacg.com/Novel/779207/")
    assert pattern.match("https://book.sfacg.com/Novel/779207/MainIndex/")
    assert pattern.match("https://book.sfacg.com/b/779207/")
    # Chapter content URLs should NOT match TOC root
    assert not pattern.match("https://book.sfacg.com/vip/c/779207/12345/")
    assert not pattern.match("https://novalpie.cc/book/12345/6789")


@pytest.mark.asyncio
async def test_clear_image_cache_scopes_active_jobs_by_workspace():
    """clear_image_cache must only clear ACTIVE_IMAGE_JOBS for the current workspace."""
    from routers.images import ACTIVE_IMAGE_JOBS, clear_image_cache

    ACTIVE_IMAGE_JOBS[("main", 1)] = {"status": "running"}
    ACTIVE_IMAGE_JOBS[("ghost", 1)] = {"status": "running"}

    db_mock = MagicMock()
    db_mock._workspace = "main"

    clear_image_cache(db=db_mock)  # sync `def` handler (runs in threadpool under FastAPI)

    # Main job must be removed, Ghost job must be preserved!
    assert ("main", 1) not in ACTIVE_IMAGE_JOBS, "Current workspace jobs should be cleared"
    assert ("ghost", 1) in ACTIVE_IMAGE_JOBS, "Other workspace jobs must be preserved"
