"""Regression: judul novel dari <title> gabungan dan link '下一章' di bab terakhir yang menunjuk ke indeks."""
import pytest

from routers.scrape import find_next_chapter_link
from services.scrapers.adaptive_dom import _clean_extracted_title, extract_universal_metadata

NOVEL = "恶役少爷怎么可能会是圣女？"


@pytest.mark.parametrize(
    "raw",
    [
        f"{NOVEL},漢唐歸來,{NOVEL}最新章节_全集TXT免费下载_千白羽的小说站手机站",
        f"{NOVEL}章节目录,{NOVEL}最新章节全集_千白羽的小说站手机版",
        f"{NOVEL}章节目录",
    ],
)
def test_clean_title_collapses_repeated_comma_segments_and_toc_suffix(raw):
    assert _clean_extracted_title(raw) == NOVEL


@pytest.mark.parametrize(
    "raw",
    ["Hello, World", "Lord of the Mysteries", "第1章 觉醒", "Re:Zero, Starting Life"],
)
def test_clean_title_leaves_ordinary_titles_untouched(raw):
    assert _clean_extracted_title(raw) == raw


def test_universal_metadata_title_from_combined_title_tag():
    html = f"<html><head><title>{NOVEL},漢唐歸來,{NOVEL}最新章节_全集TXT免费下载_千白羽的小说站手机站</title></head><body></body></html>"
    assert extract_universal_metadata(html, url="https://m.example.com/0_8/")["title"] == NOVEL


def _chapter_html(next_href):
    return f'<html><body><p>正文</p><a href="/0_8/1.html">上一章</a><a href="/0_8/">目录</a><a href="{next_href}">下一章</a></body></html>'


def test_next_link_pointing_to_index_page_is_not_a_next_chapter():
    # Bab terakhir: situs mengarahkan "下一章" kembali ke indeks buku.
    assert find_next_chapter_link(_chapter_html("/0_8/"), "https://m.example.com/0_8/157335.html") is None


def test_next_link_to_real_following_chapter_still_found():
    result = find_next_chapter_link(_chapter_html("/0_8/4781.html"), "https://m.example.com/0_8/4780.html")
    assert result == ("https://m.example.com/0_8/4781.html", "下一章")
