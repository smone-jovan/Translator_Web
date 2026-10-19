"""
Generic chapter pages: icon-only next-chapter links are found through aria-label / title / alt,
and short link-only navigation blocks inside a page-wide content wrapper stay out of the body.
"""

import pytest

from routers.scrape import find_next_chapter_link, html_to_markdown
from services.scrapers.generic_cleanup import is_vip_chapter

BASE = "https://www.generic-novel.example/ch/3"
_PROSE = "".join(
    f"<p>这是第{i}段正文，主角走进了房间。他看着窗外，心里想着明天的事情。</p>" for i in range(8)
)


def _chapter(nav: str) -> str:
    return f"<html><body><div class='chapter-content'>{_PROSE}</div>{nav}</body></html>"


# --- icon-only next-chapter links ----------------------------------------------------------

@pytest.mark.parametrize(
    "nav",
    [
        "<a href='/ch/4' aria-label='Next chapter'><i class='icon-right'></i></a>",
        "<a href='/ch/4' title='下一章'><i class='icon-right'></i></a>",
        "<a href='/ch/4'><img src='/next.png' alt='下一章'></a>",
        "<a href='/ch/4'><span class='icon' aria-label='Next page'></span></a>",
        "<a href='/ch/4' aria-label='Next chapter'>›</a>",
    ],
    ids=["aria-label", "title", "img-alt", "child-aria-label", "decoration-only-text"],
)
def test_icon_only_next_link_is_found_via_accessible_label(nav):
    result = find_next_chapter_link(_chapter(nav), BASE)

    assert result is not None
    assert result[0] == "https://www.generic-novel.example/ch/4"


def test_previous_chapter_aria_label_is_not_matched():
    nav = "<a href='/ch/2' aria-label='Previous chapter'><i class='icon-left'></i></a>"

    assert find_next_chapter_link(_chapter(nav), BASE) is None


def test_icon_links_pick_next_over_previous():
    nav = (
        "<a href='/ch/2' aria-label='Previous chapter'><i class='icon-left'></i></a>"
        "<a href='/ch/4' aria-label='Next chapter'><i class='icon-right'></i></a>"
    )

    assert find_next_chapter_link(_chapter(nav), BASE)[0] == "https://www.generic-novel.example/ch/4"


def test_icon_next_volume_label_is_excluded():
    nav = "<a href='/vol/2' aria-label='Next volume'><i class='icon-right'></i></a>"

    assert find_next_chapter_link(_chapter(nav), BASE) is None


def test_visible_text_still_wins_over_attribute_label():
    nav = "<a href='/ch/4' title='Go'>下一章</a>"

    assert find_next_chapter_link(_chapter(nav), BASE) == ("https://www.generic-novel.example/ch/4", "下一章")


# --- navigation blocks inside the content wrapper ------------------------------------------

_WRAPPER_PAGE = (
    "<html><body><div id='content'>"
    "<div class='top'><a href='/'>首页</a> <a href='/b'>书架</a></div>"
    f"<div class='txt'>{_PROSE}</div>"
    "<div class='links'><a href='/c1'>上一章</a><a href='/c3'>下一章</a></div>"
    "</div></body></html>"
)


def test_link_only_blocks_inside_content_wrapper_are_removed():
    _, markdown = html_to_markdown(_WRAPPER_PAGE, url="https://generic-novel.example/c2")

    assert "主角走进了房间" in markdown
    assert "首页" not in markdown
    assert "书架" not in markdown
    assert "上一章" not in markdown
    assert "下一章" not in markdown


def test_next_link_still_found_on_wrapper_page():
    result = find_next_chapter_link(_WRAPPER_PAGE, "https://generic-novel.example/c2")

    assert result == ("https://generic-novel.example/c3", "下一章")


def test_prose_paragraph_with_inline_link_is_kept():
    html = (
        "<html><body><div id='content'>"
        f"<div class='txt'>{_PROSE}"
        "<p>他翻开<a href='/item/7'>那本旧书</a>，发现扉页上写着一行褪色的小字。</p></div>"
        "</div></body></html>"
    )

    _, markdown = html_to_markdown(html, url="https://generic-novel.example/c2")

    assert "他翻开" in markdown
    assert "那本旧书" in markdown
    assert "发现扉页上写着一行褪色的小字" in markdown


def test_content_element_made_of_links_is_not_removed_itself():
    links = "".join(f"<a href='/w/{i}'>这是一个很长的链接文字编号{i}，用来凑足正文长度</a>" for i in range(6))
    html = f"<html><body><div class='chapter-content'>{links}</div></body></html>"

    _, markdown = html_to_markdown(html, url="https://generic-novel.example/c2")

    assert "用来凑足正文长度" in markdown


def _content_page(block: str) -> str:
    return f"<html><body><div id='content'>{_PROSE}{block}{_PROSE}</div></body></html>"


def test_linked_paywall_notice_survives_so_the_chapter_is_locked_as_vip():
    html = "<html><body><div id='content'><p><a href='/buy'>本章为付费章节，点击购买本章</a></p></div></body></html>"

    _, markdown = html_to_markdown(html, url=BASE)

    assert "本章为付费章节" in markdown
    assert is_vip_chapter(BASE, "第3章", markdown)


@pytest.mark.parametrize(
    "line, kept",
    [
        ("<p><a href='/tag/1'>李逍遥</a>？</p>", "李逍遥"),
        ("<p><a class='glossary' href='/g/2'>Dantian</a>.</p>", "Dantian"),
        ("<p><a href='/tag/1'>李逍遥</a>和<a href='/tag/2'>赵灵儿</a>？</p>", "赵灵儿"),
    ],
    ids=["single-name", "glossary-term", "two-names"],
)
def test_short_dialogue_line_with_linked_names_is_kept(line, kept):
    _, markdown = html_to_markdown(_content_page(line), url=BASE)

    assert kept in markdown


@pytest.mark.parametrize(
    "block, dropped",
    [
        ("<div><a href='/c2'>上一章</a> <a href='/toc'>目录</a> <a href='/c4'>下一章</a></div>", "目录"),
        ("<p><a href='/c2'>Previous Chapter</a> | <a href='/c4'>Next Chapter</a></p>", "Previous Chapter"),
        ("<div><a href='/'>Home</a> | <a href='/lib'>Library</a></div>", "Library"),
    ],
    ids=["cjk-pager", "english-pager", "home-menu"],
)
def test_navigation_blocks_with_nav_words_are_still_removed(block, dropped):
    _, markdown = html_to_markdown(_content_page(block), url=BASE)

    assert dropped not in markdown
