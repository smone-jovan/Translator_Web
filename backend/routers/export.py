"""
Router for exporting novel threads into various formats (EPUB, TXT).
Supports custom metadata (Author, Title, Cover) and selective chapter bundling.
"""

import os
from pathlib import Path
import io
import base64
import re
import hashlib
import asyncio
import urllib.parse
from typing import List, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

try:
    from ebooklib import epub
    HAS_EBOOKLIB = True
except ImportError:
    HAS_EBOOKLIB = False

from database import get_db, Thread, Chapter
from services.image_cacher import guess_image_ext_from_bytes, prefetch_remote_images, CACHE_DIR
from services.context_engine import ContextEngine

router = APIRouter(prefix="/api/threads", tags=["Export"])

class ExportRequest(BaseModel):
    format: str = "epub"  # "epub" or "txt"
    title: Optional[str] = None
    author: Optional[str] = "SMONE"
    cover_b64: Optional[str] = None
    cover_url: Optional[str] = None
    chapter_ids: List[int]
    hide_thoughts: bool = False

def remove_thoughts(text: str) -> str:
    """Strip <think>...</think> tags and their contents from the text."""
    if not text:
        return text
    # Strip fully enclosed tags
    cleaned = re.sub(r'<(think|thought)\b[^>]*>.*?</\1>', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Strip unclosed trailing tags
    cleaned = re.sub(r'<(think|thought)\b[^>]*>.*$', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()

def guess_image_ext(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
        return guess_image_ext_from_bytes(header)
    except Exception:
        pass
    return ""

def clean_html_content(text: str) -> str:
    """Simple converter from plain text to basic HTML for EPUB chapters."""
    # Escape basic HTML chars
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Re-enable <img> tags that were escaped
    text = re.sub(r'&lt;img\s+(.*?)&gt;', r'<img \1>', text, flags=re.DOTALL | re.IGNORECASE)

    # Process basic markdown-like formatting (non-greedy matching)
    # **bold** -> <strong>bold</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # *italic* -> <em>italic</em>
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    
    # ![alt](url) -> <img src="url" alt="alt" />
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', r'<img src="\2" alt="\1" />', text)

    # Convert newlines to <p> tags, giving image paragraphs an illustration class
    paragraphs = text.split("\n")
    html_paragraphs = []
    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        if p_clean.startswith("<img") and p_clean.endswith(">"):
            html_paragraphs.append(f'<p class="illustration">{p_clean}</p>')
        else:
            html_paragraphs.append(f'<p>{p_clean}</p>')
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

        # Collect remote URLs for pre-fetching across all chapters
        remote_urls = set()
        if request.cover_url and request.cover_url.startswith(("http://", "https://")):
            remote_urls.add(request.cover_url)
        elif thread.cover_image and thread.cover_image.startswith(("http://", "https://")):
            remote_urls.add(thread.cover_image)

        for ch in chapters:
            content = ch.content_translated or ch.content_original or ""
            for m in re.finditer(r'!\[.*?\]\((https?://[^\s\)]+)\)', content):
                remote_urls.add(m.group(1))
            for m in re.finditer(r'<img\s+[^>]*?src=["\'](https?://[^"\']+)["\']', content):
                remote_urls.add(m.group(1))

        downloaded_images = await prefetch_remote_images(list(remote_urls))

        # Handle Cover
        cover_bytes = None
        if request.cover_b64:
            b64_data = request.cover_b64
            if b64_data.startswith("/images/"):
                # Handle local image path mistakenly passed as cover_b64
                if "\x00" not in b64_data:
                    base_dir = Path("uploads/images").resolve()
                    local_rel = b64_data.replace("/images/", "", 1).lstrip("/\\")
                    try:
                        cand = (base_dir / local_rel).resolve()
                        if cand.is_relative_to(base_dir) and cand.is_file():
                            cover_bytes = cand.read_bytes()
                    except Exception:
                        pass
            else:
                try:
                    if "," in b64_data:
                        b64_data = b64_data.split(",", 1)[1]
                    cover_bytes = base64.b64decode(b64_data)
                except Exception as e:
                    print(f"⚠️ Failed to process cover base64: {e}")

        if not cover_bytes:
            cov_url = request.cover_url or thread.cover_image
            if cov_url:
                if cov_url.startswith(("http://", "https://")):
                    if cov_url in downloaded_images and downloaded_images[cov_url][0]:
                        cover_bytes = downloaded_images[cov_url][0]
                elif cov_url.startswith("/images/") and "\x00" not in cov_url:
                    base_dir = Path("uploads/images").resolve()
                    local_rel = cov_url.replace("/images/", "", 1).lstrip("/\\")
                    try:
                        cand = (base_dir / local_rel).resolve()
                        if cand.is_relative_to(base_dir) and cand.is_file():
                            cover_bytes = cand.read_bytes()
                    except Exception:
                        pass

        if cover_bytes:
            try:
                book.set_cover("cover.jpg", cover_bytes)
                print("✅ Cover image set successfully.")
            except Exception as e:
                print(f"⚠️ Failed to set cover image: {e}")

        # --- Build Chapters ---
        spine = ["nav"]
        epub_chapters = []
        toc_entries = []
        added_images = set()
        image_map = {}

        for i, ch in enumerate(chapters):
            ch_title = ch.title_translated or ch.title_original or f"Chapter {i+1}"
            ch_content = ch.content_translated or ch.content_original or "Translation not available for this chapter."

            # Jaminan Kunci Glosarium 100%: Terapkan aturan glosarium terbaru ke judul dan teks
            ch_title = ContextEngine.enforce_glossary_locking(db, thread_id, ch_title)
            ch_content = ContextEngine.enforce_glossary_locking(db, thread_id, ch_content)

            if request.hide_thoughts:
                ch_content = remove_thoughts(ch_content)

            file_name = f"chapter_{i+1}.xhtml"
            epub_ch = epub.EpubHtml(title=ch_title, file_name=file_name, lang="id")

            style = """
            body { font-family: 'Georgia', serif; line-height: 1.8; padding: 5% 8%; max-width: 680px; margin: 0 auto; color: #222; }
            h1 { text-align: center; color: #2c3e50; margin-bottom: 2em; font-size: 1.4em; border-bottom: 1px solid #ddd; padding-bottom: 0.5em; }
            p { margin-bottom: 1em; text-indent: 1.5em; }
            p.illustration { text-indent: 0; text-align: center; margin: 1.5em 0; }
            img { max-width: 100%; height: auto; display: block; margin: 0 auto; }
            """

            html_body = f"<h1>{ch_title}</h1>\n" + clean_html_content(ch_content)
            
            # Extract and bundle local & remote images
            def process_image(match):
                full_tag = match.group(0)
                img_path = match.group(1).strip()

                if img_path in image_map:
                    return full_tag.replace(img_path, image_map[img_path])

                # Case 1: Remote HTTP/HTTPS URL
                if img_path.startswith(("http://", "https://")):
                    res = downloaded_images.get(img_path)
                    if res and res[0]:
                        img_data, ext = res
                        url_hash = hashlib.sha256(img_path.encode('utf-8')).hexdigest()[:16]
                        internal_path = f"images/img_{url_hash}.{ext}"
                        if internal_path not in added_images:
                            epub_img = epub.EpubItem(
                                uid=f"img_{url_hash}",
                                file_name=internal_path,
                                media_type=f"image/{ext}",
                                content=img_data
                            )
                            book.add_item(epub_img)
                            added_images.add(internal_path)
                        image_map[img_path] = internal_path
                        return full_tag.replace(img_path, internal_path)
                    else:
                        image_map[img_path] = ""
                        return ""

                # Case 2: Local /images/ path
                if img_path.startswith("/images/"):
                    if "\x00" in img_path:
                        return full_tag
                    local_relative = img_path.replace("/images/", "", 1).lstrip("/\\")
                    base_dir = Path("uploads/images").resolve()
                    try:
                        candidate = (base_dir / local_relative).resolve()
                        is_safe = candidate.is_relative_to(base_dir) and candidate.is_file()
                    except Exception:
                        is_safe = False

                    if is_safe:
                        img_data = candidate.read_bytes()
                        ext = guess_image_ext_from_bytes(img_data) or "jpeg"
                        clean_name = re.sub(r'[^a-zA-Z0-9_.]', '_', local_relative)
                        if not clean_name.lower().endswith(f".{ext}"):
                            clean_name += f".{ext}"
                        internal_path = f"images/{clean_name}"
                        if internal_path not in added_images:
                            uid = re.sub(r'[^a-zA-Z0-9_\-]', '_', internal_path)
                            epub_img = epub.EpubItem(
                                uid=uid,
                                file_name=internal_path,
                                media_type=f"image/{ext}",
                                content=img_data
                            )
                            book.add_item(epub_img)
                            added_images.add(internal_path)
                        image_map[img_path] = internal_path
                        return full_tag.replace(img_path, internal_path)
                    else:
                        image_map[img_path] = img_path
                        return full_tag

                # Case 3: Data URI
                if img_path.startswith("data:image/"):
                    b64_match = re.match(r'data:image/([a-zA-Z0-9]+);base64,(.+)', img_path)
                    if b64_match:
                        data_type = b64_match.group(1)
                        try:
                            img_data = base64.b64decode(b64_match.group(2))
                            ext = guess_image_ext_from_bytes(img_data) or data_type or "jpeg"
                            data_hash = hashlib.sha256(img_data).hexdigest()[:16]
                            internal_path = f"images/data_{data_hash}.{ext}"
                            if internal_path not in added_images:
                                epub_img = epub.EpubItem(
                                    uid=f"data_{data_hash}",
                                    file_name=internal_path,
                                    media_type=f"image/{ext}",
                                    content=img_data
                                )
                                book.add_item(epub_img)
                                added_images.add(internal_path)
                            image_map[img_path] = internal_path
                            return full_tag.replace(img_path, internal_path)
                        except Exception:
                            pass
                    image_map[img_path] = img_path
                    return full_tag

                image_map[img_path] = img_path
                return full_tag
                
            html_body = re.sub(r'<img\s+[^>]*?src=["\'](.*?)["\'][^>]*>', process_image, html_body)

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

        def iter_chunks(stream, chunk_size=65536):
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        return StreamingResponse(
            iter_chunks(out),
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
            
            # Jaminan Kunci Glosarium 100%: Terapkan aturan glosarium terbaru ke judul dan teks
            ch_title = ContextEngine.enforce_glossary_locking(db, thread_id, ch_title)
            ch_content = ContextEngine.enforce_glossary_locking(db, thread_id, ch_content)

            if request.hide_thoughts:
                ch_content = remove_thoughts(ch_content)
                
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
