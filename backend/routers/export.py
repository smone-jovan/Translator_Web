"""
Router for exporting novel threads into various formats (EPUB, TXT).
Supports custom metadata (Author, Title, Cover) and selective chapter bundling.
"""

import io
import base64
import re
import urllib.parse
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

    # Process basic markdown-like formatting (non-greedy matching)
    # **bold** -> <strong>bold</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # *italic* -> <em>italic</em>
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)

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

        # --- Build Chapters ---
        spine = ["nav"]
        epub_chapters = []
        toc_entries = []

        for i, ch in enumerate(chapters):
            ch_title = ch.title_translated or ch.title_original or f"Chapter {i+1}"
            ch_content = ch.content_translated or "Translation not available for this chapter."

            file_name = f"chapter_{i+1}.xhtml"
            epub_ch = epub.EpubHtml(title=ch_title, file_name=file_name, lang="id")

            style = """
            body { font-family: 'Georgia', serif; line-height: 1.8; padding: 5% 8%; max-width: 680px; margin: 0 auto; color: #222; }
            h1 { text-align: center; color: #2c3e50; margin-bottom: 2em; font-size: 1.4em; border-bottom: 1px solid #ddd; padding-bottom: 0.5em; }
            p { margin-bottom: 1em; text-indent: 1.5em; }
            """

            html_body = f"<h1>{ch_title}</h1>\n" + clean_html_content(ch_content)
            epub_ch.content = f'<html xmlns="http://www.w3.org/1999/xhtml"><head><style>{style}</style></head><body>{html_body}</body></html>'

            book.add_item(epub_ch)
            spine.append(epub_ch)
            epub_chapters.append(epub_ch)
            toc_entries.append(epub.Link(file_name, ch_title, f"ch-{i+1}"))

        # --- Build HTML TOC Page ---
        toc_style = """
        body { font-family: 'Georgia', serif; padding: 6% 8%; max-width: 680px; margin: 0 auto; color: #222; }
        .toc-header { text-align: center; margin-bottom: 3em; border-bottom: 2px solid #2c3e50; padding-bottom: 1.5em; }
        .toc-header h1 { font-size: 2em; color: #2c3e50; margin-bottom: 0.3em; }
        .toc-header p { color: #666; font-size: 0.95em; font-style: italic; margin: 0; }
        .toc-title { font-size: 1.1em; font-weight: bold; color: #2c3e50; text-transform: uppercase;
                     letter-spacing: 0.12em; margin-bottom: 1.2em; }
        ol { list-style: none; padding: 0; margin: 0; }
        ol li { border-bottom: 1px solid #eee; }
        ol li a {
            display: block; padding: 0.65em 0;
            color: #1a5fa8; text-decoration: none;
            font-size: 0.97em;
            transition: color 0.2s;
        }
        ol li a:hover { color: #0d3d70; text-decoration: underline; }
        ol li .ch-num { color: #999; font-size: 0.85em; margin-right: 0.5em; }
        """

        toc_items_html = "\n".join(
            f'<li><a href="{ch.file_name}"><span class="ch-num">{str(i+1).zfill(2)}.</span> {(ch_obj.title_translated or ch_obj.title_original or f"Chapter {i+1}")}</a></li>'
            for i, (ch, ch_obj) in enumerate(zip(epub_chapters, chapters))
        )

        toc_page = epub.EpubHtml(title="Table of Contents", file_name="toc_page.xhtml", lang="id")
        toc_page.content = f"""<html xmlns="http://www.w3.org/1999/xhtml">
<head><style>{toc_style}</style></head>
<body>
  <div class="toc-header">
    <h1>{export_title}</h1>
    <p>{request.author}</p>
  </div>
  <p class="toc-title">Table of Contents</p>
  <ol>{toc_items_html}</ol>
</body>
</html>"""

        book.add_item(toc_page)

        # Insert TOC page at the front of spine (after "nav")
        spine = ["nav", toc_page] + epub_chapters

        # --- NCX/Nav TOC entries ---
        book.toc = toc_entries

        # Finalize Book
        book.add_item(epub.EpubNav())
        book.add_item(epub.EpubNcx())
        book.spine = spine

        # Save to memory
        out = io.BytesIO()
        epub.write_epub(out, book, {})
        out.seek(0)

        file_name_clean = re.sub(r'[^\w\-_.]', '_', export_title)
        filename_encoded = urllib.parse.quote(f"{file_name_clean}.epub")
        return StreamingResponse(
            out,
            media_type="application/epub+zip",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename_encoded}"}
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
        filename_encoded = urllib.parse.quote(f"{file_name_clean}.txt")
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename_encoded}"}
        )

    else:
        raise HTTPException(400, f"Unsupported format: {request.format}")
