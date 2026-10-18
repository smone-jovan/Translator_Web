"""
Generic (non-dedicated) site extraction: the ad/nav filter must not wipe out the page wrapper,
and HTML bytes must be decoded with the charset the page actually uses (GBK sites).
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from routers.scrape import decode_response_html, fetch_html_adaptive, html_to_markdown

_PROSE = "".join(
    f"<p>这是第{i}段正文，主角走进了房间。他看着窗外，心里想着明天的事情。</p>" for i in range(8)
)


# --- #1: ad filter must not remove the wrapper holding the chapter ---------------------

@pytest.mark.parametrize(
    "html",
    [
        f"<html><body class='single has-sidebar'><div class='site'><h1>第一章</h1>"
        f"<div class='entry-content'>{_PROSE}</div></div></body></html>",
        f"<html><body><div id='wrap' class='layout with-sidebar'><h1>第一章</h1>"
        f"<div id='chaptercontent'>{_PROSE}</div></div></body></html>",
        f"<html><body class='post comments-open'><article><h1>第一章</h1>{_PROSE}</article></body></html>",
    ],
    ids=["body-has-sidebar", "wrapper-with-sidebar", "body-comments-open"],
)
def test_ad_filter_keeps_wrapper_whose_class_mentions_sidebar_or_comments(html):
    _, markdown = html_to_markdown(html, url="https://generic-novel.example/ch/1")

    assert "主角走进了房间" in markdown


def test_ad_filter_still_removes_real_sidebar_and_comments():
    html = (
        "<html><body class='has-sidebar'><div class='site'>"
        f"<div class='entry-content'><h1>第一章</h1>{_PROSE}</div>"
        "<div class='sidebar'>热门推荐小说列表</div>"
        "<div id='comments'>读者评论区内容</div>"
        "</div></body></html>"
    )

    _, markdown = html_to_markdown(html, url="https://generic-novel.example/ch/1")

    assert "主角走进了房间" in markdown
    assert "热门推荐小说列表" not in markdown
    assert "读者评论区内容" not in markdown


# --- #2: charset-aware decoding -----------------------------------------------------------

def _resp(body: bytes, content_type: str = "text/html") -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": content_type},
        content=body,
        request=httpx.Request("GET", "https://generic-novel.example/ch/1"),
    )


def test_decode_uses_meta_charset_when_header_has_none():
    body = '<html><head><meta charset="gbk"></head><body>主角走进了房间</body></html>'.encode("gbk")

    assert "主角走进了房间" in decode_response_html(_resp(body))


def test_decode_uses_http_equiv_meta_charset():
    body = (
        '<html><head><meta http-equiv="Content-Type" content="text/html; charset=gb2312">'
        "</head><body>主角走进了房间</body></html>"
    ).encode("gbk")

    assert "主角走进了房间" in decode_response_html(_resp(body))


def test_decode_header_gb2312_handles_characters_outside_gb2312():
    # 镕 is in GBK/GB18030 but not GB2312; sites labelled gb2312 routinely serve GBK.
    body = "<html><body>朱镕基走进了房间</body></html>".encode("gbk")

    assert "朱镕基走进了房间" in decode_response_html(_resp(body, "text/html; charset=gb2312"))


def test_decode_sniffs_gbk_without_any_declaration():
    body = "<html><body>主角走进了房间，看着窗外。</body></html>".encode("gbk")

    assert "主角走进了房间，看着窗外。" in decode_response_html(_resp(body))


def test_decode_keeps_utf8_pages_intact():
    body = "<html><body>主角走进了房间 — café</body></html>".encode("utf-8")

    assert "主角走进了房间 — café" in decode_response_html(_resp(body))


def test_decode_undeclared_utf8_with_stray_byte_stays_utf8():
    # These bytes happen to be valid GB18030, so a strict-UTF-8-then-GB18030 chain garbles them.
    body = "<p>他笑了".encode("utf-8") + b"\xa1" + "主角走进房间</p>".encode("utf-8")

    text = decode_response_html(_resp(body))

    assert "他笑了" in text
    assert "主角走进房间" in text


def test_decode_declared_gbk_with_stray_byte_keeps_gbk():
    body = (
        '<html><head><meta charset="gbk"></head><body>主角走进了房间，看着窗外。'.encode("gbk")
        + b"\xff"
        + "他笑了。</body></html>".encode("gbk")
    )

    text = decode_response_html(_resp(body))

    assert "主角走进了房间，看着窗外。" in text
    assert "他笑了。" in text


def test_decode_ignores_unknown_declared_charset():
    body = '<html><head><meta charset="x-bogus"></head><body>主角走进了房间</body></html>'.encode("utf-8")

    assert "主角走进了房间" in decode_response_html(_resp(body, "text/html; charset=x-bogus"))


def test_decode_falls_back_to_text_for_responses_without_bytes():
    class TextOnly:
        text = "<html><body>plain</body></html>"

    assert decode_response_html(TextOnly()) == "<html><body>plain</body></html>"


@pytest.mark.asyncio
async def test_fetch_html_adaptive_decodes_gbk_page():
    body = (
        '<html><head><meta charset="gbk"><title>第一章</title></head>'
        f"<body><div id='content'>{_PROSE}</div></body></html>"
    ).encode("gbk")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_resp(body)):
        html, _ = await fetch_html_adaptive(
            "https://generic-novel.example/ch/1", allow_playwright_fallback=False
        )

    assert "主角走进了房间" in html
