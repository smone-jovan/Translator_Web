"""
Next-chapter link detection for generic sites: rel=next first, then exact labels, then a
fuzzy fallback; never 下一卷 (next volume), off-domain links, self links or javascript: hrefs.
"""

import pytest

from routers.scrape import find_next_chapter_link

BASE = "https://www.generic-novel.example/book/1/1.html"


def _page(head: str = "", body: str = "") -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


def test_link_rel_next_in_head_wins_over_body_text():
    html = _page(
        head="<link rel='next' href='/book/1/2.html'>",
        body="<a href='/news'>Next generation news</a><a href='/book/1/9.html'>下一章</a>",
    )

    assert find_next_chapter_link(html, BASE) == ("https://www.generic-novel.example/book/1/2.html", "")


def test_anchor_rel_next_wins_over_fuzzy_text():
    html = _page(body="<a href='/news'>Nextgen news</a><a rel='next' href='2.html'>→</a>")

    url, _ = find_next_chapter_link(html, BASE)

    assert url == "https://www.generic-novel.example/book/1/2.html"


@pytest.mark.parametrize("label", ["下一章", "下一页", "下一節", "Next Chapter", "next »", "下一章 >>", "[下一页]"])
def test_exact_label_wins_over_earlier_fuzzy_match(label):
    html = _page(body=f"<a href='/news'>Nextgen news</a><a href='/book/1/2.html'>{label}</a>")

    url, title = find_next_chapter_link(html, BASE)

    assert url == "https://www.generic-novel.example/book/1/2.html"
    assert title == label


def test_skips_next_volume_link():
    html = _page(body="<a href='/book/1/vol2.html'>下一卷</a><a href='/book/1/2.html'>下一页</a>")

    url, _ = find_next_chapter_link(html, BASE)

    assert url == "https://www.generic-novel.example/book/1/2.html"


def test_skips_off_domain_links_but_allows_sibling_subdomain():
    html = _page(
        body="<a href='https://ads.other-site.example/x'>下一章</a>"
        "<a href='https://m.generic-novel.example/book/1/2.html'>下一章</a>"
    )

    url, _ = find_next_chapter_link(html, BASE)

    assert url == "https://m.generic-novel.example/book/1/2.html"


def test_skips_off_domain_rel_next():
    html = _page(
        head="<link rel='next' href='https://tracker.other-site.example/p2'>",
        body="<a href='/book/1/2.html'>下一章</a>",
    )

    url, _ = find_next_chapter_link(html, BASE)

    assert url == "https://www.generic-novel.example/book/1/2.html"


def test_skips_self_and_javascript_links():
    html = _page(
        body="<a href='javascript:void(0)'>下一章</a><a href='#'>下一章</a>"
        "<a href='/book/1/1.html'>下一章</a><a href='/book/1/2.html'>下一章</a>"
    )

    url, _ = find_next_chapter_link(html, BASE)

    assert url == "https://www.generic-novel.example/book/1/2.html"


def test_fuzzy_fallback_when_no_exact_label():
    html = _page(body="<a href='/book/1/2.html'>点击进入下一章节</a>")

    url, title = find_next_chapter_link(html, BASE)

    assert url == "https://www.generic-novel.example/book/1/2.html"
    assert title == "点击进入下一章节"


def test_returns_none_when_no_next_link():
    html = _page(body="<a href='/book/1/'>目录</a><a href='/book/1/vol2.html'>下一卷</a>")

    assert find_next_chapter_link(html, BASE) is None
