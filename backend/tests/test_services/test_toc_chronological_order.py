"""Daftar bab dari situs yang menampilkan 'terbaru dulu' harus dibalik agar Bab 1 = bab pertama cerita."""
import pytest

from routers.toc import ensure_chronological_order


def _ch(title, url):
    return {"title": title, "url": url}


def test_descending_numbers_in_titles_are_reversed():
    chapters = [_ch(f"第{n}章 标题", f"https://x.example/b/{n}.html") for n in (5, 4, 3, 2, 1)]

    result = ensure_chronological_order(chapters)

    assert [c["title"][:3] for c in result] == ["第1章", "第2章", "第3章", "第4章", "第5章"]


def test_volume_prefixed_titles_use_chapter_number_not_volume():
    # Pola nyata xiaoxiaoshuo8: "第五卷 175~..." menurun
    chapters = [_ch(f"第五卷 {n}~标题", f"https://x.example/0_8/{n}.html") for n in (175, 174, 173, 167)]

    result = ensure_chronological_order(chapters)

    assert [c["url"].rsplit("/", 1)[1] for c in result] == ["167.html", "173.html", "174.html", "175.html"]


def test_chinese_numeral_titles_descending_are_reversed():
    chapters = [
        _ch("第一千八百七十一章 后记", "https://x.example/b/9.html"),
        _ch("第一千八百六十四章 野心", "https://x.example/b/8.html"),
        _ch("第一千八百六十三章 来临", "https://x.example/b/7.html"),
        _ch("第一千八百六十二章 其他", "https://x.example/b/6.html"),
    ]

    result = ensure_chronological_order(chapters)

    assert result[0]["title"].startswith("第一千八百六十二章")


def test_url_ids_decide_when_titles_have_no_numbers():
    chapters = [_ch(f"标题{x}", f"https://x.example/b/{n}.html") for x, n in zip("甲乙丙丁", (400, 300, 200, 100))]

    result = ensure_chronological_order(chapters)

    assert [c["url"].rsplit("/", 1)[1] for c in result] == ["100.html", "200.html", "300.html", "400.html"]


def test_ascending_list_is_left_untouched():
    chapters = [_ch(f"第{n}章 标题", f"https://x.example/b/{n}.html") for n in (1, 2, 3, 4, 5)]

    assert ensure_chronological_order(chapters) == chapters


def test_short_or_ambiguous_list_is_left_untouched():
    two = [_ch("第2章", "https://x.example/2.html"), _ch("第1章", "https://x.example/1.html")]
    mixed = [_ch(f"第{n}章", f"https://x.example/{n}.html") for n in (1, 5, 2, 6, 3)]

    assert ensure_chronological_order(two) == two
    assert ensure_chronological_order(mixed) == mixed


def test_does_not_mutate_input():
    chapters = [_ch(f"第{n}章", f"https://x.example/{n}.html") for n in (3, 2, 1)]
    snapshot = list(chapters)

    ensure_chronological_order(chapters)

    assert chapters == snapshot


@pytest.mark.asyncio
async def test_scrape_toc_endpoint_returns_oldest_first(monkeypatch):
    from routers import toc as toc_router

    descending = [_ch(f"第{n}章 标题", f"https://novel.example/b/{n}.html") for n in (6, 5, 4, 3, 2, 1)]

    async def fake_fetch(url, client=None, workspace=None):
        return "书名", descending, []

    monkeypatch.setattr(toc_router, "fetch_and_extract_links", fake_fetch)

    resp = await toc_router.scrape_toc(toc_router.TOCScrapeRequest(url="https://novel.example/b/"), None)

    assert [c["title"][:3] if isinstance(c, dict) else c.title[:3] for c in resp.chapters][0] == "第1章"
