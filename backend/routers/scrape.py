"""
POST /api/scrape — Fetch URL, clean HTML, return Markdown.
Uses httpx + BeautifulSoup (lightweight, no browser needed).
Also contains URL imports and NovelUpdates/SFACG metadata scrapers.
"""

import re
import urllib.parse
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import select

from database import get_db, Thread, Chapter, GlobalSetting
from services.scrapers.engine import MetadataScraperEngine

router = APIRouter(prefix="/api", tags=["Scraping"])
scraper_engine = MetadataScraperEngine()


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    title: str
    markdown: str
    word_count: int


class ImportURLRequest(BaseModel):
    url: str


class ScrapeMetadataRequest(BaseModel):
    original_title: Optional[str] = None
    include_cover: bool = True
    search_by: Optional[str] = "original"  # "original" or "translated"
    source: Optional[str] = "novelupdates"   # "novelupdates" or "sfacg"


# Tags to strip completely
STRIP_TAGS = [
    "script", "style", "nav", "footer", "header", "aside",
    "iframe", "noscript", "form", "button", "svg", "figure",
    "figcaption", "img", "video", "audio", "canvas",
]

# Common ad/nav class patterns
AD_PATTERNS = re.compile(
    r"(ad[s_-]|banner|sidebar|menu|nav|footer|comment|social|share|popup|modal|cookie)",
    re.IGNORECASE,
)


def html_to_markdown(html: str) -> tuple[str, str]:
    """Convert HTML to clean markdown-ish text. Returns (title, content)."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"

    # Remove unwanted tags
    for tag_name in STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove elements with ad-like classes/ids
    for el in soup.find_all(True):
        classes = " ".join(el.get("class", []))
        el_id = el.get("id", "")
        if AD_PATTERNS.search(classes) or AD_PATTERNS.search(el_id):
            el.decompose()

    # Try to find main content area
    content_el = (
        soup.find("article")
        or soup.find("div", class_=re.compile(r"(chapter|content|entry|post|text|body)", re.I))
        or soup.find("main")
        or soup.body
        or soup
    )

    # Pre-process some tags to maintain structure
    for br in content_el.find_all("br"):
        br.replace_with("\n")
    
    for p in content_el.find_all("p"):
        p.insert_before("\n\n")
        p.insert_after("\n\n")

    # Convert to text with paragraph breaks
    lines = []
    
    processed_tags = set()

    for el in content_el.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "div"]):
        if el in processed_tags:
            continue
            
        # Check if this element is a meaningful block of text
        # For DIVs, we only want them if they are "leaf" nodes in terms of text structure
        if el.name == "div":
            # If it has other block elements inside, let those be processed individually
            if el.find(["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li"]):
                continue
            # If it has other DIVs inside, skip this one and let the children be processed
            if el.find("div"):
                continue
        
        text = el.get_text(strip=True)
        if not text or len(text) < 2: # Ignore very short artifacts
            continue

        # Mark children as processed to avoid double-dipping
        for child in el.find_all(True):
            processed_tags.add(child)

        tag = el.name
        if tag.startswith("h"):
            level = int(tag[1])
            lines.append(f"\n{'#' * level} {text}\n")
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "blockquote":
            lines.append(f"> {text}")
        else:
            # For p and div, we just add the text block
            lines.append(f"\n{text}\n")

    markdown = "\n".join(lines).strip()
    
    # Fallback: if markdown is still empty, just try to get all text from body
    if not markdown:
        print("⚠️ No structured content found, falling back to simple text extraction")
        markdown = content_el.get_text(separator="\n\n", strip=True)

    # Collapse excessive newlines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)

    return title, markdown


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_url(req: ScrapeRequest):
    """Fetch URL, strip ads/nav, return clean markdown."""
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TranslatorBot/1.0)"},
        ) as client:
            resp = await client.get(req.url)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Failed to fetch URL: {e}")

    title, markdown = html_to_markdown(resp.text)

    if not markdown:
        raise HTTPException(422, "No content extracted from URL.")

    return ScrapeResponse(
        title=title,
        markdown=markdown,
        word_count=len(markdown.split()),
    )


@router.post("/threads/import-url")
async def import_from_url(req: ImportURLRequest, db: Session = Depends(get_db)):
    """Scrape a URL and create a new Thread/Chapter for it."""
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TranslatorBot/1.0)"},
        ) as client:
            resp = await client.get(req.url)
            resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch URL: {e}")

    title, markdown = html_to_markdown(resp.text)
    if not markdown:
        raise HTTPException(422, "No content extracted from URL.")

    # Create Thread
    thread = Thread(
        title=title,
        original_title=title,
        source_type="url",
        source_url=req.url
    )
    db.add(thread)
    db.flush() # Get ID

    # Create first chapter
    chapter = Chapter(
        thread_id=thread.id,
        order=0,
        title_original=title, # Often URL is just one chapter
        content_original=markdown
    )
    db.add(chapter)
    db.commit()

    return {"thread_id": thread.id, "chapter_id": chapter.id}


@router.post("/threads/{thread_id}/scrape_metadata")
async def scrape_metadata(
    thread_id: int,
    req: ScrapeMetadataRequest,
    db: Session = Depends(get_db)
):
    """Scrape metadata from Novel Updates or SFACG directly."""
    # 1. Fetch thread
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    query = req.original_title or thread.source_url or thread.title or ""
    if not query:
        raise HTTPException(400, "No query title or URL available to scrape metadata")

    # Call swappable scraper coordinator
    result = await scraper_engine.scrape(
        query=query,
        source=req.source,
        search_by=req.search_by,
        include_cover=req.include_cover,
        db_session=db
    )

    if not result.success:
        raise HTTPException(500, result.synopsis or "Failed to scrape metadata")

    # Persist scraped fields to DB Thread
    thread.original_title = result.original_title
    if result.title:
        thread.title = result.title
    if result.genres:
        thread.genres = result.genres
    if result.tags:
        thread.tags = result.tags
    if result.synopsis:
        thread.synopsis = result.synopsis
    if result.status_coo:
        thread.status_coo = result.status_coo
    if result.status:
        thread.status = result.status
    if result.cover_image:
        thread.cover_image = result.cover_image
    if result.author:
        thread.author = result.author
        
    db.commit()
    
    return {
        "success": True,
        "original_title": result.original_title,
        "title": result.title,
        "author": result.author,
        "genres": result.genres,
        "tags": result.tags,
        "status": result.status,
        "status_coo": result.status_coo,
        "synopsis": result.synopsis,
        "cover_image": result.cover_image,
        "detail_url": result.detail_url
    }
