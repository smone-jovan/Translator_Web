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
    """Strip HTML tags, return clean text. Falls back to raw HTML if text is empty."""
    if isinstance(html_content, bytes):
        # Try to detect encoding or fallback to utf-8
        try:
            html_str = html_content.decode("utf-8")
        except UnicodeDecodeError:
            html_str = html_content.decode("latin-1", errors="ignore")
    else:
        html_str = html_content

    soup = BeautifulSoup(html_str, "html.parser")

    # Remove script/style
    for tag in soup.find_all(["script", "style", "nav", "footer"]):
        tag.decompose()

    # Try structured extraction
    text = soup.get_text(separator="\n", strip=True)

    # Fallback: if text is empty but HTML exists, return stripped HTML
    if not text.strip() and html_str.strip():
        print("⚠️ BeautifulSoup get_text failed, using fallback extraction")
        # Just remove tags but keep content
        import re
        text = re.sub(r'<[^>]+>', '\n', html_str)
        text = re.sub(r'\n{2,}', '\n\n', text)

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

    # Extract chapters following the Spine (proper reading order)
    chapters_info = []
    order = 0
    
    # Get spine items
    spine_items = []
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
            spine_items.append(item)

    for item in spine_items:
        try:
            raw_html = item.get_content()
            text = extract_text_from_html(raw_html)

            # Skip very short items (TOC, cover, title page, etc.)
            # But be more lenient: some short chapters might exist
            if len(text) < 20:
                print(f"ℹ️ Skipping short EPUB item '{item.get_name()}' (Length: {len(text)})")
                continue

            title = guess_chapter_title(item, order)
            print(f"✅ Extracted Chapter {order+1}: {title} ({len(text)} chars)")
            print(f"   Preview: {text[:50]}...")

            chapter = Chapter(
                thread_id=thread.id,
                order=order,
                title_original=title,
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
        except Exception as e:
            print(f"⚠️ Failed to process EPUB item '{item.get_name()}': {e}")
            continue

    db.commit()

    return EpubResponse(
        thread_id=thread.id,
        title=book_title,
        total_chapters=len(chapters_info),
        chapters=chapters_info,
    )
