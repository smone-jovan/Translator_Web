import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Thread, Chapter
from services.scrapers.novalpie import NovalpieAdapter
from services.scrapers.base import ScrapedNovelMetadata

client = TestClient(app)

@pytest.mark.asyncio
async def test_novalpie_get_next_chapter():
    adapter = NovalpieAdapter()
    
    mock_chapters = [
        {"order": 1, "title": "Chapter 1", "url": "https://novalpie.cc/book/352285/5831032"},
        {"order": 2, "title": "Chapter 2", "url": "https://novalpie.cc/book/352285/5831046"},
        {"order": 3, "title": "Chapter 3", "url": "https://novalpie.cc/book/352285/5831097"},
    ]
    
    with patch.object(adapter, "scrape_toc", new_callable=AsyncMock) as mock_toc:
        mock_toc.return_value = ("Test Novel", mock_chapters)
        
        # Next from Ch 1 -> Ch 2
        next_info = await adapter.get_next_chapter("https://novalpie.cc/book/352285/5831032")
        assert next_info is not None
        assert next_info[0] == "https://novalpie.cc/book/352285/5831046"
        assert next_info[1] == "Chapter 2"
        
        # Next from Ch 2 -> Ch 3
        next_info2 = await adapter.get_next_chapter("https://novalpie.cc/book/352285/5831046")
        assert next_info2 is not None
        assert next_info2[0] == "https://novalpie.cc/book/352285/5831097"
        assert next_info2[1] == "Chapter 3"
        
        # Next from Ch 3 (last) -> None
        next_info3 = await adapter.get_next_chapter("https://novalpie.cc/book/352285/5831097")
        assert next_info3 is None

@pytest.mark.asyncio
async def test_novalpie_get_remaining_chapters():
    adapter = NovalpieAdapter()
    
    mock_meta = ScrapedNovelMetadata(
        success=True,
        title="Becoming a Dragon in Cyberpunk",
        original_title="成为赛博朋克中的龙",
        author="짱빠른토끼",
        cover_image="https://images.novelpia.com/cover/test.file",
        synopsis="Dragon in cyberpunk story"
    )
    mock_chapters = [
        {"order": 1, "title": "Chapter 1", "url": "https://novalpie.cc/book/352285/5831032"},
        {"order": 2, "title": "Chapter 2", "url": "https://novalpie.cc/book/352285/5831046"},
        {"order": 3, "title": "Chapter 3", "url": "https://novalpie.cc/book/352285/5831097"},
    ]
    
    with patch.object(adapter, "scrape_metadata", new_callable=AsyncMock) as mock_m:
        mock_m.return_value = mock_meta
        with patch.object(adapter, "scrape_toc", new_callable=AsyncMock) as mock_toc:
            mock_toc.return_value = ("成为赛博朋克中的龙", mock_chapters)
            
            meta, remaining = await adapter.get_remaining_chapters("https://novalpie.cc/book/352285/5831032")
            assert meta is not None
            assert meta.original_title == "成为赛博朋克中的龙"
            assert meta.author == "짱빠른토끼"
            assert len(remaining) == 2
            assert remaining[0]["url"] == "https://novalpie.cc/book/352285/5831046"
            assert remaining[1]["url"] == "https://novalpie.cc/book/352285/5831097"

def test_import_from_url_auto_populates_novalpie_thread():
    mock_meta = ScrapedNovelMetadata(
        success=True,
        title="Becoming a Dragon in Cyberpunk",
        original_title="成为赛博朋克中的龙",
        author="짱빠른토끼",
        cover_image="https://images.novelpia.com/cover/test.file",
        synopsis="Dragon in cyberpunk story"
    )
    mock_remaining = [
        {"order": 2, "title": "Chapter 2", "url": "https://novalpie.cc/book/352285/5831046"},
        {"order": 3, "title": "Chapter 3", "url": "https://novalpie.cc/book/352285/5831097"},
    ]
    
    with patch("services.scrapers.novalpie.NovalpieAdapter.scrape_chapter_content", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = ("Chapter 1 序幕", "This is chapter 1 content.")
        with patch("services.scrapers.novalpie.NovalpieAdapter.get_remaining_chapters", new_callable=AsyncMock) as mock_rem:
            mock_rem.return_value = (mock_meta, mock_remaining)
            
            resp = client.post("/api/threads/import-url", json={"url": "https://novalpie.cc/book/352285/5831032"})
            assert resp.status_code == 200
            data = resp.json()
            thread_id = data["thread_id"]
            
            with SessionLocal() as db:
                th = db.get(Thread, thread_id)
                assert th is not None
                assert th.title == "成为赛博朋克中的龙"
                assert th.author == "짱빠른토끼"
                assert th.cover_image == "https://images.novelpia.com/cover/test.file"
                
                chapters = db.query(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order.asc()).all()
                assert len(chapters) == 3
                
                # Ch 0 has content
                assert chapters[0].order == 0
                assert chapters[0].title_original == "Chapter 1 序幕"
                assert chapters[0].content_original == "This is chapter 1 content."
                
                # Ch 1 and 2 are stubs
                assert chapters[1].order == 1
                assert chapters[1].title_original == "Chapter 2"
                assert chapters[1].content_original is None
                assert chapters[1].source_url == "https://novalpie.cc/book/352285/5831046"
                
                assert chapters[2].order == 2
                assert chapters[2].title_original == "Chapter 3"
                assert chapters[2].content_original is None
                assert chapters[2].source_url == "https://novalpie.cc/book/352285/5831097"
                
                # Cleanup
                db.query(Chapter).where(Chapter.thread_id == thread_id).delete()
                db.delete(th)
                db.commit()

def test_fetch_next_chapter_novalpie():
    with SessionLocal() as db:
        th = Thread(title="Test Novel", source_type="url", source_url="https://novalpie.cc/book/352285")
        db.add(th)
        db.flush()
        
        ch1 = Chapter(
            thread_id=th.id,
            order=0,
            title_original="Chapter 1",
            content_original="Content 1",
            source_url="https://novalpie.cc/book/352285/5831032"
        )
        db.add(ch1)
        db.commit()
        
        th_id = th.id
        ch1_id = ch1.id

    with patch("services.scrapers.novalpie.NovalpieAdapter.get_next_chapter", new_callable=AsyncMock) as mock_next:
        mock_next.return_value = ("https://novalpie.cc/book/352285/5831046", "Chapter 2")
        with patch("services.scrapers.novalpie.NovalpieAdapter.scrape_chapter_content", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = ("Chapter 2", "Content 2")
            
            resp = client.post(f"/api/threads/{th_id}/chapters/{ch1_id}/fetch-next")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            new_ch_id = data["chapter_id"]
            
            with SessionLocal() as db:
                new_ch = db.get(Chapter, new_ch_id)
                assert new_ch is not None
                assert new_ch.order == 1
                assert new_ch.title_original == "Chapter 2"
                assert new_ch.content_original == "Content 2"
                assert new_ch.source_url == "https://novalpie.cc/book/352285/5831046"
                
                # Cleanup
                db.query(Chapter).where(Chapter.thread_id == th_id).delete()
                th_del = db.get(Thread, th_id)
                if th_del:
                    db.delete(th_del)
                db.commit()
