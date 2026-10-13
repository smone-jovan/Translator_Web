import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.scrapers.sfacg import SFACGAdapter


def test_extract_novel_id():
    adapter = SFACGAdapter()
    assert adapter.extract_novel_id("https://book.sfacg.com/Novel/779207/MainIndex/") == 779207
    assert adapter.extract_novel_id("https://book.sfacg.com/Novel/779207/") == 779207
    assert adapter.extract_novel_id("https://book.sfacg.com/b/779207/") == 779207
    assert adapter.extract_novel_id("779207") == 779207
    assert adapter.extract_novel_id("https://book.sfacg.com/Novel/abc/") is None
    assert adapter.extract_novel_id("invalid-query") is None


@pytest.mark.asyncio
async def test_scrape_metadata_clean_title():
    adapter = SFACGAdapter()
    html_sample = """
    <html>
      <body>
        <div class="d-summary">
          <h1 class="title">
            <span class="text">我不想成为里世界女主角啊！
              <span class="tag blue">VIP</span>
              <span class="tag green">征文大赛长篇</span>
            </span>
          </h1>
          <div class="introduce">测试简介内容</div>
        </div>
        <div class="author-name">九色猫</div>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_sample

    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        meta = await adapter.scrape_metadata("https://book.sfacg.com/Novel/779207/")

        assert meta.success is True
        assert meta.title == "我不想成为里世界女主角啊！"
        assert meta.author == "九色猫"
        assert meta.synopsis == "测试简介内容"


@pytest.mark.asyncio
async def test_scrape_toc_success():
    adapter = SFACGAdapter()
    html_sample = """
    <html>
      <head><title>目录列表</title></head>
      <body>
        <h1 class="story-title">我不想成为里世界女主角啊！</h1>
        <ul class="catalog-list">
          <li>
            <a href="/Novel/779207/1035376/9806896/" title="第一章 为了帝皇！">
              第一章 为了帝皇！
            </a>
          </li>
          <li>
            <a href="/vip/c/9866457/" title="第七十九章 你要一起洗吗？">
              <span class="icn_vip">VIP</span> 第七十九章 你要一起洗吗？
            </a>
          </li>
        </ul>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_sample

    with patch("services.scrapers.sfacg.create_safe_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_factory.return_value = mock_client

        title, chapters = await adapter.scrape_toc("https://book.sfacg.com/Novel/779207/MainIndex/")

        assert title == "我不想成为里世界女主角啊！"
        assert len(chapters) == 2
        assert chapters[0]["title"] == "第一章 为了帝皇！"
        assert chapters[0]["url"] == "https://book.sfacg.com/Novel/779207/1035376/9806896/"
        assert chapters[1]["title"] == "第七十九章 你要一起洗吗？"
        assert chapters[1]["url"] == "https://book.sfacg.com/vip/c/9866457/"


@pytest.mark.asyncio
async def test_scrape_toc_invalid_id():
    adapter = SFACGAdapter()
    with pytest.raises(ValueError) as exc:
        await adapter.scrape_toc("https://book.sfacg.com/Novel/invalid/")
    assert "Could not extract a valid SFACG novel ID" in str(exc.value)


@pytest.mark.asyncio
async def test_scrape_toc_router_endpoint():
    from routers.toc import scrape_toc, TOCScrapeRequest

    mock_chapters = [
        {"title": "第一章", "url": "https://book.sfacg.com/Novel/779207/1/1/"}
    ]

    with patch("services.scrapers.sfacg.SFACGAdapter.scrape_toc", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = ("我不想成为里世界女主角啊！", mock_chapters)
        req = TOCScrapeRequest(url="https://book.sfacg.com/Novel/779207/MainIndex/")
        res = await scrape_toc(req)

        assert res.title == "我不想成为里世界女主角啊！"
        assert len(res.chapters) == 1
        assert res.chapters[0].title == "第一章"


@pytest.mark.asyncio
async def test_scrape_chapter_content_free_success():
    adapter = SFACGAdapter()
    html_sample = """
    <html>
      <body>
        <h1 class="article-title">第一章 为了帝皇！</h1>
        <div id="ChapterBody" class="article-content font16">
          <p>昏暗的房间里，冷光映出一张脸。</p>
          <p>林远神情专注。</p>
        </div>
        <div class="chapter-pager">
          <a href="/Novel/779207/1035376/9807529/">下一章</a>
        </div>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_sample

    with patch("services.scrapers.sfacg.create_safe_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_factory.return_value = mock_client

        title, markdown = await adapter.scrape_chapter_content("https://book.sfacg.com/Novel/779207/1035376/9806896/")

        assert title == "第一章 为了帝皇！"
        assert "昏暗的房间里" in markdown
        assert "林远神情专注" in markdown


@pytest.mark.asyncio
async def test_scrape_chapter_content_vip_locked():
    adapter = SFACGAdapter()
    html_sample = """
    <html>
      <body>
        <h1 class="article-title">第七十九章 你要一起洗吗？</h1>
        <div id="ChapterBody" class="article-content font16">
          <p>晚餐过后，就在林愿帮江韵收拾好餐具时...</p>
        </div>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_sample

    with patch("services.scrapers.sfacg.create_safe_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_factory.return_value = mock_client

        title, markdown = await adapter.scrape_chapter_content("https://book.sfacg.com/vip/c/9866457/")

        assert title == "第七十九章 你要一起洗吗？"
        assert "[VIP CHAPTER]" in markdown


@pytest.mark.asyncio
async def test_get_next_chapter():
    adapter = SFACGAdapter()
    html_sample = """
    <html>
      <body>
        <div class="chapter-pager">
          <a href="/Novel/779207/1035376/9807529/">下一章</a>
        </div>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_sample

    with patch("services.scrapers.sfacg.create_safe_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_factory.return_value = mock_client

        next_info = await adapter.get_next_chapter("https://book.sfacg.com/Novel/779207/1035376/9806896/")

        assert next_info is not None
        assert next_info[0] == "https://book.sfacg.com/Novel/779207/1035376/9807529/"
        assert next_info[1] == "下一章"


