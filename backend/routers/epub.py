"""
POST /api/upload-epub — Parse EPUB file, split into chapters, save to DB.
"""

import io
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

try:
    import ebooklib
    from ebooklib import epub
    HAS_EBOOKLIB = True
except ImportError:
    HAS_EBOOKLIB = False

from database import get_db, Thread, Chapter

router = APIRouter(prefix="/api", tags=["EPUB"])


class ChapterInfo(BaseModel):
    id: int
    order: int
    title: str
    preview: str
    word_count: int


class EpubResponse(BaseModel):
    thread_id: int
    title: str
    total_chapters: int
    chapters: list[ChapterInfo]


def extract_text_from_html(html_content: bytes | str) -> str:
    """Strip HTML tags, return clean text."""
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script/style
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Collapse blank lines
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def guess_chapter_title(item, index: int) -> str:
    """Try to get chapter title from EPUB item."""
    # Try to extract first heading
    content = item.get_content()
    soup = BeautifulSoup(content, "html.parser")
    heading = soup.find(["h1", "h2", "h3", "h4"])
    if heading:
        title = heading.get_text(strip=True)
        if title and len(title) < 200:
            return title

    # Fallback to item title or filename
    item_title = getattr(item, "title", None)
    if item_title:
        return item_title

    return f"Chapter {index + 1}"


@router.post("/upload-epub", response_model=EpubResponse)
async def upload_epub(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload EPUB, parse into chapters, store in DB."""
    if not HAS_EBOOKLIB:
        raise HTTPException(500, "ebooklib not installed. Run: pip install ebooklib")

    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(400, "File must be .epub")

    content = await file.read()

    try:
        book = epub.read_epub(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(422, f"Failed to parse EPUB: {e}")

    # Get book title
    book_title = "Unknown"
    dc_title = book.get_metadata("DC", "title")
    if dc_title:
        book_title = dc_title[0][0]

    # Create thread
    thread = Thread(title=book_title, source_type="epub")
    db.add(thread)
    db.flush()

    # Extract chapters (document items only)
    chapters_info = []
    order = 0
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        raw_html = item.get_content()
        text = extract_text_from_html(raw_html)

        # Skip very short items (TOC, cover, etc.)
        if len(text) < 50:
            continue

        title = guess_chapter_title(item, order)

        chapter = Chapter(
            thread_id=thread.id,
            order=order,
            title=title,
            content_original=text,
        )
        db.add(chapter)
        db.flush()

        chapters_info.append(ChapterInfo(
            id=chapter.id,
            order=order,
            title=title,
            preview=text[:150] + "..." if len(text) > 150 else text,
            word_count=len(text.split()),
        ))
        order += 1

    db.commit()

    return EpubResponse(
        thread_id=thread.id,
        title=book_title,
        total_chapters=len(chapters_info),
        chapters=chapters_info,
    )
