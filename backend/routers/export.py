"""
Router for exporting novel threads into various formats (EPUB, TXT).
Supports custom metadata (Author, Title, Cover) and selective chapter bundling.
"""

import io
import base64
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

try:
    from ebooklib import epub
    HAS_EBOOKLIB = True
except ImportError:
    HAS_EBOOKLIB = False

from database import get_db, Thread, Chapter

router = APIRouter(prefix="/api/threads", tags=["Export"])

class ExportRequest(BaseModel):
    format: str = "epub"  # "epub" or "txt"
    title: Optional[str] = None
    author: Optional[str] = "SMONE"
    cover_b64: Optional[str] = None
    cover_url: Optional[str] = None
    chapter_ids: List[int]

def clean_html_content(text: str) -> str:
    """Simple converter from plain text to basic HTML for EPUB chapters."""
    # Escape basic HTML chars
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert newlines to <p> tags
    paragraphs = text.split("\n")
    html_paragraphs = [f"<p>{p.strip()}</p>" for p in paragraphs if p.strip()]
    return "\n".join(html_paragraphs)

@router.post("/{thread_id}/export")
async def export_thread(
    thread_id: int,
    request: ExportRequest,
    db: Session = Depends(get_db)
):
    """
    Export selected chapters from a thread into a book file.
    Only uses translated content (titles and bodies).
    """
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")

    # Fetch selected chapters in order
    chapters = (
        db.query(Chapter)
        .filter(Chapter.id.in_(request.chapter_ids))
        .filter(Chapter.thread_id == thread_id)
        .order_by(Chapter.order.asc())
        .all()
    )

    if not chapters:
        raise HTTPException(400, "No valid chapters selected for export")

    export_title = request.title or thread.title or "Exported Novel"
    
    if request.format == "epub":
        if not HAS_EBOOKLIB:
            raise HTTPException(500, "ebooklib not installed on server")

        book = epub.EpubBook()
        book.set_identifier(f"ai-trans-thread-{thread_id}")
        book.set_title(export_title)
        book.set_language("id")
        book.add_author(request.author)

        # Handle Cover
        if request.cover_b64:
            try:
                b64_data = request.cover_b64
                if "," in b64_data:
                    b64_data = b64_data.split(",")[1]
                image_bytes = base64.b64decode(b64_data)
                book.set_cover("cover.jpg", image_bytes)
            except Exception as e:
                print(f"⚠️ Failed to process cover image: {e}")
        elif request.cover_url:
            try:
                import httpx
                print(f"📥 Downloading cover image from: {request.cover_url}")
                # Fetch image bytes
                with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                    resp = client.get(request.cover_url)
                    if resp.status_code == 200:
                        book.set_cover("cover.jpg", resp.content)
                        print(f"✅ Cover image downloaded and set successfully.")
                    else:
                        print(f"⚠️ Failed to download cover image. Status code: {resp.status_code}")
            except Exception as e:
                print(f"⚠️ Error downloading cover image: {e}")

        # Add Chapters
        spine = ["nav"]
        for i, ch in enumerate(chapters):
            # Use translated title or original title or fallback
            ch_title = ch.title_translated or ch.title_original or f"Chapter {i+1}"
            ch_content = ch.content_translated or "Translation not available for this chapter."
            
            # Create EPUB chapter
            file_name = f"chapter_{i+1}.xhtml"
            epub_ch = epub.EpubHtml(title=ch_title, file_name=file_name, lang="id")
            
            # Basic Premium Styling for Content
            style = """
            body { font-family: 'Georgia', serif; line-height: 1.6; padding: 5%; }
            h1 { text-align: center; color: #2c3e50; margin-bottom: 2em; }
            p { margin-bottom: 1em; text-indent: 1em; }
            """
            
            html_body = f"<h1>{ch_title}</h1>\n" + clean_html_content(ch_content)
            epub_ch.content = f'<html><head><style>{style}</style></head><body>{html_body}</body></html>'
            
            book.add_item(epub_ch)
            spine.append(epub_ch)

        # Finalize Book
        book.add_item(epub.EpubNav())
        book.spine = spine
        
        # Save to memory
        out = io.BytesIO()
        epub.write_epub(out, book, {})
        out.seek(0)
        
        file_name_clean = re.sub(r'[^\w\-_.]', '_', export_title)
        return StreamingResponse(
            out,
            media_type="application/epub+zip",
            headers={"Content-Disposition": f"attachment; filename={file_name_clean}.epub"}
        )

    elif request.format == "txt":
        out = io.StringIO()
        out.write(f"TITLE: {export_title}\n")
        out.write(f"AUTHOR: {request.author}\n")
        out.write("-" * 40 + "\n\n")
        
        for i, ch in enumerate(chapters):
            ch_title = ch.title_translated or ch.title_original or f"Chapter {i+1}"
            ch_content = ch.content_translated or "Translation not available."
            out.write(f"=== {ch_title} ===\n\n")
            out.write(ch_content + "\n\n")
            out.write("-" * 20 + "\n\n")
            
        content = out.getvalue().encode("utf-8")
        out.close()
        
        file_name_clean = re.sub(r'[^\w\-_.]', '_', export_title)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={file_name_clean}.txt"}
        )

    else:
        raise HTTPException(400, f"Unsupported format: {request.format}")
