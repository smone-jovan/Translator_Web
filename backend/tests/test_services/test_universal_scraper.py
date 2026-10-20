"""Comprehensive tests for Universal Plug-and-Play Scraper upgrades (P1a, P1b, P2a, P2b, P3)."""

from unittest.mock import AsyncMock
import httpx
import pytest

from database import Chapter, Thread
from routers import scrape as scrape_router
from routers import toc as toc_router
from routers.scrape import (
    decode_response_html,
    find_next_chapter_link,
    find_next_subpage_link,
    html_to_markdown,
    stitch_subpages_markdown,
)
from routers.toc import extract_links_from_html
from services.scrapers.adaptive_dom import extract_hydration_prose, extract_universal_metadata
from services.scrapers.engine import MetadataScraperEngine


def test_p1a_html_to_markdown_strips_hidden_honeypots_and_preserves_lazy_images():
    html = """
    <html>
      <head><title>第1章 觉醒</title></head>
      <body>
        <article class="chapter-content">
          <h1>第1章 觉醒</h1>
          <p>第一段正常的小说正文内容，描述主角在山巅之上凝视远方，心中涌起万丈豪情。</p>
          <span style="display: none">盗版网站水印请勿转载12345</span>
          <p style="font-size:0px;">隐藏防盗干扰乱码文字ABCDEFG</p>
          <div hidden>本段文字被hidden属性隐藏不应出现在结果中</div>
          <span aria-hidden="true">ARIA隐藏文字干扰项</span>
          <img data-src="/uploads/illust_01.jpg" alt="插图一" />
          <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" width="1" height="1" />
          <p>第二段正常的小说正文内容，紧接着插图之后继续展开精彩的战斗描写与对话。</p>
        </article>
      </body>
    </html>
    """
    title, md = html_to_markdown(html, url="https://lightnovel.example.org/read/10/1.html")
    assert title == "第1章 觉醒"
    assert "第一段正常的小说正文内容" in md
    assert "第二段正常的小说正文内容" in md
    assert "![插图一](https://lightnovel.example.org/uploads/illust_01.jpg)" in md
    assert "盗版网站水印" not in md
    assert "隐藏防盗干扰" not in md
    assert "hidden属性隐藏" not in md
    assert "ARIA隐藏文字" not in md
    assert "data:image" not in md


def test_p1b_find_next_subpage_and_multilingual_next_chapter_links():
    # Split chapter page 1: has both 下一页 (101_2.html) and 下一章 (102.html)
    html_split = """
    <html><body>
      <div class="Readpage">
        <a href="/book/99/100.html">上一章</a>
        <a href="/book/99/">目录</a>
        <a href="/book/99/101_2.html">下一页</a>
        <a href="/book/99/102.html">下一章</a>
      </div>
    </body></html>
    """
    base_url = "https://biquge.example.org/book/99/101.html"
    assert find_next_subpage_link(html_split, base_url) == "https://biquge.example.org/book/99/101_2.html"
    assert find_next_chapter_link(html_split, base_url) == ("https://biquge.example.org/book/99/102.html", "下一章")

    # Single-page chapter: no subpage link
    html_single = '<html><body><a href="/book/99/102.html">下一章</a></body></html>'
    assert find_next_subpage_link(html_single, base_url) is None

    # Korean next chapter link (while ignoring 다음권 = next volume)
    html_kr = """
    <html><body>
      <a href="https://novel.kr.example/view/100">다음권</a>
      <a href="https://novel.kr.example/view/12">다음화</a>
    </body></html>
    """
    assert find_next_chapter_link(html_kr, "https://novel.kr.example/view/11") == (
        "https://novel.kr.example/view/12",
        "다음화",
    )

    # Japanese and Indonesian labels + JS next_page fallback
    html_id = '<html><body><a href="/baca/2">Bab Selanjutnya &raquo;</a></body></html>'
    assert find_next_chapter_link(html_id, "https://indo-novel.example/baca/1") == (
        "https://indo-novel.example/baca/2",
        "Bab Selanjutnya »",
    )

    html_js = '<html><body><script>var next_page = "/txt/88/105.html";</script></body></html>'
    assert find_next_chapter_link(html_js, "https://cn.example.org/txt/88/104.html") == (
        "https://cn.example.org/txt/88/105.html",
        "",
    )


def test_p1b_fetch_next_chapter_stitches_split_subpages(client, db_session, monkeypatch):
    thread = Thread(title="Split Chapter Book", source_url="https://biquge.example.org/book/99/")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    ch1 = Chapter(
        thread_id=thread.id,
        order=1,
        title_original="第1章 开端",
        source_url="https://biquge.example.org/book/99/101.html",
        content_original="第1章正文",
        translation_status="idle",
    )
    db_session.add(ch1)
    db_session.commit()
    db_session.refresh(ch1)

    pages = {
        "https://biquge.example.org/book/99/101.html": (
            '<html><body><a href="/book/99/101_2.html">下一页</a></body></html>'
        ),
        "https://biquge.example.org/book/99/101_2.html": (
            '<html><body><a href="/book/99/102.html">下一章</a></body></html>'
        ),
        "https://biquge.example.org/book/99/102.html": (
            "<html><body><h1>第2章 进阶 (1/2)</h1>"
            "<article class='chapter-content'><p>" + ("第二章上半部分正文内容。" * 8) + "</p></article>"
            '<a href="/book/99/102_2.html">下一页</a></body></html>'
        ),
        "https://biquge.example.org/book/99/102_2.html": (
            "<html><body><h1>第2章 进阶 (2/2)</h1>"
            "<article class='chapter-content'><p>" + ("第二章下半部分合并正文内容。" * 8) + "</p></article>"
            '<a href="/book/99/103.html">下一章</a></body></html>'
        ),
    }

    async def fake_fetch(url: str, *, workspace=None):
        return pages[url], url

    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", AsyncMock(side_effect=fake_fetch))
    monkeypatch.setattr(scrape_router, "validate_external_url", lambda u: None)
    monkeypatch.setattr("services.security.validate_external_url", lambda u: None)

    resp = client.post(f"/api/threads/{thread.id}/chapters/{ch1.id}/fetch-next")
    assert resp.status_code == 200
    data = resp.json()
    ch2 = db_session.get(Chapter, data["chapter_id"])
    assert ch2.source_url == "https://biquge.example.org/book/99/102.html"
    assert "第二章上半部分正文内容" in ch2.content_original
    assert "第二章下半部分合并正文内容" in ch2.content_original


def test_p2a_toc_tail_deduplication_and_multilingual_links():
    toc_html = """
    <html>
      <head>
        <meta property="og:novel:book_name" content="万古神帝" />
        <title>万古神帝_最新章节_某某小说网</title>
      </head>
      <body>
        <div class="listmain">
          <dl>
            <dt>《万古神帝》最新章节（提示：已启用缓存技术）</dt>
            <dd><a href="/read/888/3.html">第3章 终局</a></dd>
            <dd><a href="/read/888/2.html">第2章 激战</a></dd>
            <dt>《万古神帝》正文</dt>
            <dd><a href="/read/888/0.html">楔子 陨落</a></dd>
            <dd><a href="/read/888/1.html">第1章 重生</a></dd>
            <dd><a href="/read/888/2.html">第2章 激战</a></dd>
            <dd><a href="/read/888/3.html">第3章 终局</a></dd>
          </dl>
        </div>
      </body>
    </html>
    """
    novel_title, links, _ = extract_links_from_html(toc_html, "https://novel.example.org/book/888.html")
    assert novel_title == "万古神帝"
    assert [c["title"] for c in links] == ["楔子 陨落", "第1章 重生", "第2章 激战", "第3章 终局"]

    # Korean & Japanese TOC links
    kr_html = """
    <html>
      <head><title>전지적 독자 시점 - 소설</title></head>
      <body>
        <ul>
          <li><a href="/viewer/10/1">프롤로그</a></li>
          <li><a href="/viewer/10/2">1화 유료 서비스 시작</a></li>
          <li><a href="/viewer/10/3">2화 주인공</a></li>
        </ul>
      </body>
    </html>
    """
    _, kr_links, _ = extract_links_from_html(kr_html, "https://kr.example.org/novel/10")
    assert len(kr_links) == 3
    assert kr_links[0]["title"] == "프롤로그"
    assert kr_links[1]["title"] == "1화 유료 서비스 시작"


@pytest.mark.asyncio
async def test_p2b_universal_metadata_extractor_and_engine_adapter(monkeypatch):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Book",
          "name": "Omniscient Reader",
          "author": {"@type": "Person", "name": "Sing Shong"},
          "image": "/images/orv-cover.jpg",
          "description": "Only I know the end of this world.",
          "genre": ["Fantasy", "Apocalypse"]
        }
        </script>
        <meta property="og:novel:status" content="Completed" />
      </head>
      <body><h1>Omniscient Reader</h1></body>
    </html>
    """
    meta = extract_universal_metadata(html, url="https://generic-novel.example/series/orv")
    assert meta["title"] == "Omniscient Reader"
    assert meta["author"] == "Sing Shong"
    assert meta["cover_image"] == "https://generic-novel.example/images/orv-cover.jpg"
    assert meta["synopsis"] == "Only I know the end of this world."
    assert meta["genres"] == "Fantasy, Apocalypse"
    assert meta["status"] == "Completed"

    async def fake_fetch(url: str, *, workspace=None):
        assert workspace == "ghost"
        return html, url

    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", fake_fetch)
    engine = MetadataScraperEngine()
    res = await engine.scrape("https://generic-novel.example/series/orv", workspace="ghost")
    assert res.success is True
    assert res.title == "Omniscient Reader"
    assert res.author == "Sing Shong"
    assert res.cover_image == "https://generic-novel.example/images/orv-cover.jpg"


def test_p3_decode_big5_shift_jis_euc_kr_and_next_data_hydration():
    # Big5
    big5_html = '<html><head><meta charset="big5"></head><body><h1>第一章 劍道</h1></body></html>'
    resp_big5 = httpx.Response(200, content=big5_html.encode("big5"), request=httpx.Request("GET", "https://tw.test/1"))
    assert "第一章 劍道" in decode_response_html(resp_big5)

    # Shift-JIS
    sjis_html = '<html><head><meta charset="shift_jis"></head><body><h1>第1話 転生</h1></body></html>'
    resp_sjis = httpx.Response(200, content=sjis_html.encode("shift_jis"), request=httpx.Request("GET", "https://jp.test/1"))
    assert "第1話 転生" in decode_response_html(resp_sjis)

    # EUC-KR
    euckr_html = '<html><head><meta charset="euc-kr"></head><body><h1>1화 회귀</h1></body></html>'
    resp_kr = httpx.Response(200, content=euckr_html.encode("euc-kr"), request=httpx.Request("GET", "https://kr.test/1"))
    assert "1화 회귀" in decode_response_html(resp_kr)

    # Next.js __NEXT_DATA__ hydration fallback when static body is an empty shell
    prose_text = "这是存储在Next.js水合JSON中的长篇小说章节正文内容，即使静态DOM节点为空也能直接提取出来。" * 3
    spa_html = f"""
    <html>
      <head><title>SPA Reader</title></head>
      <body>
        <div id="__next"></div>
        <script id="__NEXT_DATA__" type="application/json">
        {{"props": {{"pageProps": {{"chapter": {{"chapterTitle": "第99章 虚空降临", "chapterContent": "{prose_text}"}}}}}}}}
        </script>
      </body>
    </html>
    """
    title, md = html_to_markdown(spa_html, url="https://spa-novel.example/read/99")
    assert title == "第99章 虚空降临"
    assert "这是存储在Next.js水合JSON中的长篇小说章节正文内容" in md


def test_p2b_import_url_and_bulk_toc_auto_populate_universal_metadata(client, db_session, monkeypatch):
    ch_html = """
    <html>
      <head>
        <meta property="og:novel:book_name" content="星辰之主" />
        <meta property="og:novel:author" content="减肥专家" />
        <meta property="og:image" content="/covers/xingchen.jpg" />
        <meta property="og:description" content="世纪之交，人类懵懂着踏入星空。" />
        <meta property="og:novel:category" content="科幻" />
      </head>
      <body>
        <h1>第一章 群星召唤</h1>
        <article class="chapter-content">
          <p>这是第一章的正文内容，包含足够的文字长度以便通过系统对非VIP章节的长度校验。</p>
          <p>第二段正文内容继续描述主角在星空学院中的经历与考核过程。</p>
        </article>
      </body>
    </html>
    """

    async def fake_fetch(url: str, *, workspace=None):
        return ch_html, url

    monkeypatch.setattr(scrape_router, "fetch_html_adaptive", AsyncMock(side_effect=fake_fetch))
    monkeypatch.setattr(scrape_router, "validate_external_url", lambda u: None)
    monkeypatch.setattr("services.security.validate_external_url", lambda u: None)

    # 1. Single chapter import (/api/threads/import-url)
    resp = client.post("/api/threads/import-url", json={"url": "https://generic-cn.example/book/77/1.html"})
    assert resp.status_code == 200
    tid = resp.json()["thread_id"]
    thread = db_session.get(Thread, tid)
    assert thread.title == "星辰之主"
    assert thread.author == "减肥专家"
    assert thread.cover_image == "https://generic-cn.example/covers/xingchen.jpg"
    assert thread.synopsis == "世纪之交，人类懵懂着踏入星空。"

    # 2. Bulk TOC import (/api/threads/bulk-import-toc)
    resp2 = client.post(
        "/api/threads/bulk-import-toc",
        json={
            "base_url": "https://generic-cn.example/book/77/",
            "chapters": [
                {"title": "第一章 群星召唤", "url": "https://generic-cn.example/book/77/1.html"},
                {"title": "第二章 启航", "url": "https://generic-cn.example/book/77/2.html"},
            ],
        },
    )
    assert resp2.status_code == 200
    tid2 = resp2.json()["thread_id"]
    thread2 = db_session.get(Thread, tid2)
    assert thread2.title == "星辰之主"
    assert thread2.author == "减肥专家"
    assert thread2.cover_image == "https://generic-cn.example/covers/xingchen.jpg"
    assert thread2.genres == "科幻"


def test_p3_stealth_base_imports_and_extracts_clean_chapter():
    from services.scrapers.stealth_base import StealthyNovelAdapter

    html = """
    <html>
      <body>
        <h1 class="ep-title">Episode 1: Awakening</h1>
        <div class="novel-body">
          <p>First paragraph of the episode with plenty of narrative prose content for adaptive extraction.</p>
          <p>Second paragraph continuing the scene seamlessly.</p>
        </div>
      </body>
    </html>
    """
    title, content = StealthyNovelAdapter.extract_clean_chapter(
        html, ".ep-title", ".novel-body", adaptive=True, domain="example.com"
    )
    assert title == "Episode 1: Awakening"
    assert "First paragraph of the episode" in content
    assert "Second paragraph continuing" in content
