import urllib.parse
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database import get_db, Thread, Chapter, resolve_workspace, get_db_workspace

router = APIRouter(prefix="/api", tags=["Scraping", "TOC"])

class TOCScrapeRequest(BaseModel):
    url: str

class TOCChapterInfo(BaseModel):
    title: str
    url: str

class TOCScrapeResponse(BaseModel):
    title: str
    chapters: List[TOCChapterInfo]

class TOCBulkImportRequest(BaseModel):
    thread_id: Optional[int] = None
    title: Optional[str] = None
    base_url: Optional[str] = None
    genres: Optional[str] = None
    chapters: List[TOCChapterInfo]

async def fetch_and_extract_links(url: str, client: httpx.AsyncClient):
    resp = await client.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    title_tag = soup.find("title")
    novel_title = title_tag.get_text(strip=True) if title_tag else "Untitled Novel"

    base_url = str(resp.url)
    parsed_base = urllib.parse.urlparse(base_url)

    links = []
    seen_urls = set()
    raw_links = []

    for a in soup.find_all('a', href=True):
        href = a.get('href')
        text = a.get_text(strip=True)
        if not text or len(text) < 2:
            continue
            
        abs_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(abs_url)
        
        if parsed.netloc != parsed_base.netloc:
            continue
            
        if abs_url == base_url or abs_url in seen_urls:
            continue
            
        raw_links.append((text, abs_url, parsed))
        
        is_chapter = False
        junk_paths = ["/stag/", "/cmts/", "/lcmt/", "/fans", "/vip/c/"]
        
        # 1. Path is deeper than base (e.g. /Novel/123/456/)
        if parsed.path.startswith(parsed_base.path) and len(parsed.path.rstrip('/')) > len(parsed_base.path.rstrip('/')):
            if not any(junk in parsed.path for junk in junk_paths):
                is_chapter = True
        # 2. Chinese websites often use specific path structures, but make sure it's not the novel root itself
        elif any(char.isdigit() for char in parsed.path) and len(parsed.path.rstrip('/').split('/')) > 3:
            if not any(junk in parsed.path for junk in junk_paths):
                is_chapter = True

        # Extra safety: Ensure the link is not just the novel homepage
        if "/Novel/" in parsed.path and len(parsed.path.rstrip('/').split('/')) <= 3:
            is_chapter = False

        if is_chapter:
            links.append({"title": text, "url": abs_url})
            seen_urls.add(abs_url)

    return novel_title, links, raw_links

def is_domain(url: str, domain: str) -> bool:
    """Check if URL host matches domain or subdomain exactly."""
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        return host == domain or host.endswith(f".{domain}")
    except Exception:
        return False


@router.post("/threads/scrape-toc", response_model=TOCScrapeResponse)
async def scrape_toc(req: TOCScrapeRequest, request: Request = None):
    """Scrape a novel index/TOC page and detect chapter links heuristically or via dedicated adapters."""
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    ws = resolve_workspace(request)

    # SSRF guard: block requests to internal/private IPs
    from services.security import validate_external_url, create_safe_async_client
    validate_external_url(req.url)

    # 1. Dedicated Adapter: Novalpie.cc
    if is_domain(req.url, "novalpie.cc"):
        try:
            from services.scrapers.novalpie import NovalpieAdapter
            novalpie = NovalpieAdapter(workspace=ws)
            novel_title, chapters_list = await novalpie.scrape_toc(req.url)
            toc_chapters = [TOCChapterInfo(title=c["title"], url=c["url"]) for c in chapters_list]
            return TOCScrapeResponse(title=novel_title, chapters=toc_chapters)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape novalpie.cc TOC: {e}")

    # 2. Dedicated Adapter: SFACG (book.sfacg.com)
    if is_domain(req.url, "sfacg.com"):
        try:
            from services.scrapers.sfacg import SFACGAdapter
            sfacg = SFACGAdapter()
            novel_title, chapters_list = await sfacg.scrape_toc(req.url)
            toc_chapters = [TOCChapterInfo(title=c["title"], url=c["url"]) for c in chapters_list]
            return TOCScrapeResponse(title=novel_title, chapters=toc_chapters)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape sfacg.com TOC: {e}")

    try:
        async with create_safe_async_client(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TranslatorBot/1.0)"},
        ) as client:
            novel_title, links, raw_links = await fetch_and_extract_links(req.url, client)

            # If we found too few links, we might be on the summary page.
            # Look for a dedicated TOC link (like /MainIndex/ or "点击阅读")
            if len(links) < 50:
                toc_url = None
                for text, url, parsed in raw_links:
                    if "/MainIndex/" in url or "目录" in text or "点击阅读" in text:
                        toc_url = url
                        break

                if toc_url:
                    validate_external_url(toc_url)
                    print(f"[TOC Scraper] Found <50 links. Automatically following TOC link: {toc_url}")
                    novel_title2, links2, _ = await fetch_and_extract_links(toc_url, client)
                    if len(links2) > len(links):
                        novel_title = novel_title2
                        links = links2

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch URL: {e}")

    return TOCScrapeResponse(title=novel_title, chapters=links)


@router.post("/threads/bulk-import-toc")
async def bulk_import_toc(req: TOCBulkImportRequest, db: Session = Depends(get_db)):
    """Bulk import chapters from TOC. Only saves the source_url, content is scraped on-demand."""
    if not req.chapters:
        raise HTTPException(400, "No chapters provided")

    if req.thread_id:
        thread = db.execute(select(Thread).where(Thread.id == req.thread_id)).scalar_one_or_none()
        if not thread:
            raise HTTPException(404, "Thread not found")

        max_order_val = db.execute(
            select(func.max(Chapter.order)).where(Chapter.thread_id == thread.id)
        ).scalar()
        max_order = -1 if max_order_val is None else max_order_val
    else:
        title = req.title or "Imported Novel"
        author = ""
        synopsis = ""
        cover_image = ""

        # Auto-fetch metadata if base_url is provided
        if req.base_url:
            from services.security import validate_external_url
            try:
                validate_external_url(req.base_url)
                if is_domain(req.base_url, "sfacg.com"):
                    from services.scrapers.sfacg import SFACGAdapter
                    sfacg = SFACGAdapter()
                    meta = await sfacg.scrape_metadata(req.base_url)
                    if meta.success:
                        title = meta.title or title
                        author = meta.author or ""
                        synopsis = meta.synopsis or ""
                        cover_image = meta.cover_image or ""
                elif is_domain(req.base_url, "novalpie.cc"):
                    ws = get_db_workspace(db)
                    from services.scrapers.novalpie import NovalpieAdapter
                    novalpie = NovalpieAdapter(workspace=ws)
                    meta = await novalpie.scrape_metadata(req.base_url)
                    if meta.success:
                        title = meta.title or title
                        author = meta.author or ""
                        synopsis = meta.synopsis or ""
                        cover_image = meta.cover_image or ""
                        if not req.genres and meta.genres:
                            req.genres = meta.genres
            except Exception as e:
                print(f"[TOC Import] Auto-metadata failed: {e}")


        # Create new Thread
        thread = Thread(
            title=title,
            original_title=title,
            author=author,
            synopsis=synopsis,
            cover_image=cover_image,
            genres=req.genres,
            source_type="url",
            source_url=req.base_url or (req.chapters[0].url if req.chapters else "")
        )
        db.add(thread)
        db.flush()
        max_order = -1

    new_chapters = []
    for idx, chap_info in enumerate(req.chapters):
        chapter = Chapter(
            thread_id=thread.id,
            order=max_order + 1 + idx,
            title_original=chap_info.title,
            source_url=chap_info.url,
            content_original=None,  # explicitly null so it triggers on-demand scraping
            translation_status="idle"
        )
        new_chapters.append(chapter)

    db.add_all(new_chapters)
    db.commit()

    return {
        "success": True, 
        "thread_id": thread.id, 
        "imported_count": len(new_chapters)
    }
