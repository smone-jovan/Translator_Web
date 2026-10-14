import inspect
import socket
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


def test_novalpie_prefers_patchright_if_available():
    """_get_thread_browser should import patchright if available, otherwise playwright."""
    import services.scrapers.novalpie as novalpie_mod
    source = inspect.getsource(novalpie_mod._get_thread_browser)
    assert "patchright" in source, "_get_thread_browser must support patchright as drop-in upgrade"
    assert "playwright" in source, "_get_thread_browser must retain standard playwright fallback"


def test_stealth_base_class_structure():
    """StealthyNovelAdapter must inherit from BaseScraperAdapter and provide required methods."""
    from services.scrapers.stealth_base import StealthyNovelAdapter
    from services.scrapers.base import BaseScraperAdapter

    assert issubclass(StealthyNovelAdapter, BaseScraperAdapter)
    adapter = StealthyNovelAdapter(workspace="ghost")
    assert adapter.workspace == "ghost"
    assert hasattr(adapter, "fetch_stealth_page")
    assert hasattr(adapter, "fetch_stealth_batch")
    assert hasattr(adapter, "extract_clean_chapter")


@pytest.mark.asyncio
async def test_stealth_base_ssrf_protection(monkeypatch):
    """fetch_stealth_page and fetch_stealth_batch must validate URLs against SSRF before fetching."""
    from services.scrapers.stealth_base import StealthyNovelAdapter

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ],
    )

    adapter = StealthyNovelAdapter()

    # fetch_stealth_page must raise HTTPException 400 on private IP
    with pytest.raises(HTTPException) as exc_page:
        await adapter.fetch_stealth_page("http://127.0.0.1:8000/secret")
    assert exc_page.value.status_code == 400
    assert "private or local network resources is forbidden" in exc_page.value.detail

    # fetch_stealth_batch must raise HTTPException 400 on private IP
    with pytest.raises(HTTPException) as exc_batch:
        await adapter.fetch_stealth_batch(["http://127.0.0.1:8000/batch1", "https://example.com/ch2"])
    assert exc_batch.value.status_code == 400


def test_stealth_base_extract_clean_chapter():
    """extract_clean_chapter parses clean title and markdown paragraphs from a mock Scrapling page."""
    from services.scrapers.stealth_base import StealthyNovelAdapter

    mock_title_node = MagicMock()
    mock_title_node.text = "  Chapter 1: The Dragon Awakens  "

    mock_p1 = MagicMock()
    mock_p1.text = "In a faraway land, magic was fading."
    mock_p2 = MagicMock()
    mock_p2.text = "A young hunter found an ancient egg."

    mock_content_node = MagicMock()
    mock_content_node.css.return_value = [mock_p1, mock_p2]

    mock_page = MagicMock()
    def css_side_effect(selector, **kwargs):
        if "title" in selector or "h1" in selector:
            return [mock_title_node]
        return [mock_content_node]

    mock_page.css.side_effect = css_side_effect

    title, markdown = StealthyNovelAdapter.extract_clean_chapter(
        mock_page,
        title_selector="h1.title",
        content_selector="#chapter-content"
    )

    assert title == "Chapter 1: The Dragon Awakens"
    assert "In a faraway land, magic was fading." in markdown
    assert "A young hunter found an ancient egg." in markdown
