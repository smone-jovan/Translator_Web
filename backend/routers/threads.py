"""
Thread & Chapter management endpoints.
GET /api/threads — list all
GET /api/threads/{id} — detail + chapters
DELETE /api/threads/{id} — delete thread + cascade
GET /api/threads/{id}/chapters/{chapter_id} — single chapter content
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func
from typing import List, Optional
import asyncio

from database import get_db, Thread, Chapter, GlobalSetting, UserBookmark
from routers.scrape import html_to_markdown, AD_PATTERNS
import httpx

router = APIRouter(prefix="/api", tags=["Threads"])

class ImportURLRequest(BaseModel):
    url: str


class ChapterOut(BaseModel):
    id: int
    order: int
    title_original: Optional[str]
    title_translated: Optional[str]
    word_count: int
    has_translation: bool
    translation_status: str

    class Config:
        from_attributes = True


class ThreadItemOut(BaseModel):
    id: int
    title: str
    source_type: str
    source_url: Optional[str]
    chapter_count: int
    created_at: Optional[str]
    last_read: Optional[str] = None
    progress: int = 0


class ThreadDetail(ThreadItemOut):
    chapters: List[ChapterOut]


class TranslationSegmentOut(BaseModel):
    id: int
    order: int
    original_text: Optional[str]
    translated_text: Optional[str]
    display_mode: str

    class Config:
        from_attributes = True


class ChapterContent(BaseModel):
    id: int
    order: int
    title_original: Optional[str]
    title_translated: Optional[str]
    content_original: Optional[str]
    content_translated: Optional[str]
    translation_status: Optional[str]
    segments: List[TranslationSegmentOut] = []


@router.get("/threads", response_model=List[ThreadItemOut])
def list_threads(db: Session = Depends(get_db)):
    """List all threads with reading progress."""
    stmt = select(Thread).order_by(Thread.id.desc())
    threads = db.execute(stmt).scalars().all()
    
    result = []
    for t in threads:
        # Chapter count
        ch_count_stmt = select(func.count(Chapter.id)).where(Chapter.thread_id == t.id)
        ch_count = db.execute(ch_count_stmt).scalar() or 0
        
        # Last read info from UserBookmark
        bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == t.id)
        bookmark = db.execute(bookmark_stmt).scalar_one_or_none()
        
        last_read_title = None
        progress = 0
        
        if bookmark:
            last_ch_stmt = select(Chapter).where(Chapter.id == bookmark.chapter_id)
            last_ch = db.execute(last_ch_stmt).scalar_one_or_none()
            if last_ch:
                last_read_title = last_ch.title_translated or last_ch.title_original
                # Calculate progress percentage
                if ch_count > 0:
                    progress = int(((last_ch.order + 1) / ch_count) * 100)
        
        result.append(ThreadItemOut(
            id=t.id,
            title=t.title,
            source_type=t.source_type,
            source_url=t.source_url,
            chapter_count=ch_count,
            created_at=str(t.created_at) if t.created_at else None,
            last_read=last_read_title,
            progress=progress
        ))
    return result


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
def get_thread(thread_id: int, db: Session = Depends(get_db)):
    """Get thread with chapter list."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    
    if not thread:
        raise HTTPException(404, "Thread not found")

    ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order)
    chapters = db.execute(ch_stmt).scalars().all()

    ch_out = [
        ChapterOut(
            id=c.id,
            order=c.order,
            title_original=c.title_original,
            title_translated=c.title_translated,
            word_count=len((c.content_original or "").split()),
            has_translation=bool(c.content_translated),
            translation_status=c.translation_status
        )
        for c in chapters
    ]

    return ThreadDetail(
        id=thread.id,
        title=thread.title,
        source_type=thread.source_type,
        source_url=thread.source_url,
        chapter_count=len(ch_out),
        created_at=str(thread.created_at) if thread.created_at else None,
        chapters=ch_out,
    )


@router.get("/threads/{thread_id}/chapters/{chapter_id}", response_model=ChapterContent)
def get_chapter(thread_id: int, chapter_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Get single chapter with full content."""
    stmt = select(Chapter).where(Chapter.id == chapter_id, Chapter.thread_id == thread_id)
    chapter = db.execute(stmt).scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    # Update bookmark (Background history)
    bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id)
    bookmark = db.execute(bookmark_stmt).scalar_one_or_none()
    if not bookmark:
        bookmark = UserBookmark(thread_id=thread_id, chapter_id=chapter_id)
        db.add(bookmark)
    else:
        bookmark.chapter_id = chapter_id
    db.commit()

    # --- PREFETCH TRIGGER (ADR-009) ---
    from services.background_translator import BackgroundTranslator
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    target_lang = gs.target_language if gs else "Indonesian"
    model = gs.lm_model if gs else None
    ai_url = gs.lm_url if gs else "http://localhost:1234"

    # 1. Trigger background translation for CURRENT chapter if untranslated
    if chapter.translation_status == "idle" and not chapter.content_translated:
        background_tasks.add_task(
            BackgroundTranslator.run_chapter_translation,
            chapter_id=chapter_id,
            thread_id=thread_id,
            target_lang=target_lang,
            model=model,
            lm_url=ai_url
        )

    # 2. Trigger prefetch check for NEXT chapter
    background_tasks.add_task(
        BackgroundTranslator.check_and_prefetch,
        current_chapter_id=chapter_id,
        thread_id=thread_id,
        target_lang=target_lang,
        model=model,
        lm_url=ai_url
    )

    return ChapterContent(
        id=chapter.id,
        order=chapter.order,
        title_original=chapter.title_original,
        title_translated=chapter.title_translated,
        content_original=chapter.content_original,
        content_translated=chapter.content_translated,
        translation_status=chapter.translation_status,
        segments=[
            TranslationSegmentOut(
                id=s.id,
                order=s.order,
                original_text=s.original_text,
                translated_text=s.translated_text,
                display_mode=s.display_mode,
            ) for s in chapter.segments
        ]
    )


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, db: Session = Depends(get_db)):
    """Delete thread + all chapters + lorebook (cascade)."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    db.delete(thread)
    db.commit()
    return {"deleted": True, "id": thread_id}


class TranslationUpdate(BaseModel):
    translated_text: str

@router.put("/threads/{thread_id}/chapters/{chapter_id}/translation")
def update_chapter_translation(thread_id: int, chapter_id: int, body: TranslationUpdate, db: Session = Depends(get_db)):
    """Save the translated text back to the chapter."""
    stmt = select(Chapter).where(Chapter.id == chapter_id, Chapter.thread_id == thread_id)
    chapter = db.execute(stmt).scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
        
    chapter.content_translated = body.translated_text
    db.commit()
    return {"status": "saved"}


@router.post("/threads/{thread_id}/translate-titles")
async def translate_titles(
    thread_id: int, 
    target_lang: str = "Indonesian", 
    repolish: bool = False,
    chapter_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Bulk translate or polish titles in a thread."""
    from services.ai_provider import AIProvider
    import re

    # Get server-side settings
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    lm_url = gs.lm_url if gs else "http://localhost:1234"

    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    
    if not thread:
        raise HTTPException(404, "Thread not found")

    if chapter_id:
        ch_stmt = select(Chapter).where(Chapter.id == chapter_id, Chapter.thread_id == thread_id)
        chapters = db.execute(ch_stmt).scalars().all()
    else:
        ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order)
        chapters = db.execute(ch_stmt).scalars().all()

    if not chapters:
        return {"count": 0}

    titles_to_process = []
    indices = [] # -1 for thread title, >=0 for actual chapter objects

    # If full thread polishing and not specific chapter
    if not chapter_id:
        if thread.title and any(ord(char) > 127 for char in thread.title):
            titles_to_process.append(thread.title)
            indices.append(-1)

    for i, c in enumerate(chapters):
        # Process if untranslated OR if repolish requested
        if c.title_original and (not c.title_translated or repolish):
            titles_to_process.append(c.title_original)
            indices.append(i)

    if not titles_to_process:
        return {"count": 0}

    # Chunking logic optimized for ~8000 context window
    CHUNK_SIZE = 50
    total_count = 0
    
    for start_idx in range(0, len(titles_to_process), CHUNK_SIZE):
        if start_idx > 0:
            await asyncio.sleep(1.0) # Breath for LM Studio
            
        end_idx = start_idx + CHUNK_SIZE
        chunk_titles = titles_to_process[start_idx:end_idx]
        chunk_indices = indices[start_idx:end_idx]
        
        prompt_lines = []
        for i, title in enumerate(chunk_titles):
            # We use the relative index within the chunk for the prompt label
            # But the label must match the absolute index in chunk_indices
            abs_idx = chunk_indices[i]
            label = "BOOK_TITLE" if abs_idx == -1 else f"CHAPTER_{abs_idx}"
            prompt_lines.append(f"[{label}]: {title}")

        sys_prompt = (
            f"You are a professional literary editor and translator specializing in {target_lang}. \n"
            "Task: Translate and creatively polish these chapter titles.\n\n"
            "Requirements:\n"
            "1. Maintain EXACT label format (e.g., [BOOK_TITLE]: or [CHAPTER_0]:).\n"
            "2. Titles should feel 'Polished' and 'Cool', not just literal translations.\n"
            "3. Remove excessive Pinyin or redundant chapter numbers if they exist in the text.\n"
            "4. Return one polished title per line."
        )
        user_prompt = "\n".join(prompt_lines)

        try:
            print(f"🔄 Processing title batch {start_idx//CHUNK_SIZE + 1}...")
            response = await AIProvider.generate_batch(sys_prompt, user_prompt, base_url=lm_url)
            translated_lines = [line.strip() for line in response.split("\n") if line.strip()]
            
            for line in translated_lines:
                if ":" not in line: continue
                # Handle cases where label might have square brackets
                parts = line.split(":", 1)
                label = parts[0].strip()
                translated_title = parts[1].strip()

                if "BOOK_TITLE" in label:
                    thread.title = translated_title
                    total_count += 1
                elif "CHAPTER_" in label:
                    try:
                        # Extract digit from CHAPTER_X
                        match = re.search(r"CHAPTER_(\d+)", label)
                        if match:
                            ch_idx = int(match.group(1))
                            if 0 <= ch_idx < len(chapters):
                                chapters[ch_idx].title_translated = translated_title
                                total_count += 1
                    except Exception as e:
                        print(f"⚠️ Skip line '{line}': {e}")
            
            db.commit() # Commit each chunk
        except Exception as e:
            print(f"❌ Batch Error at chunk {start_idx}: {e}")
            # Continue to next chunk if one fails? Or raise?
            # Let's raise to alert user if the connection is dead
            raise HTTPException(500, f"AI Error at chunk {start_idx}: {str(e)}")

    return {"count": total_count}

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
