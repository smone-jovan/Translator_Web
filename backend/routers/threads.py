"""
Thread & Chapter management endpoints.
GET /api/threads — list all
GET /api/threads/{id} — detail + chapters
DELETE /api/threads/{id} — delete thread + cascade
GET /api/threads/{id}/chapters/{chapter_id} — single chapter content
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func
from typing import List, Optional
import asyncio

from database import get_db, Thread, Chapter, GlobalSetting, UserBookmark
from routers.scrape import html_to_markdown, AD_PATTERNS
import httpx

router = APIRouter(prefix="/api", tags=["Threads"])

def clean_and_format_chapter_title(title: str, order_num: int, total_chapters: int, volume_num: int = None) -> str:
    """
    Cleans chapter title of redundant numbers, prefixes (e.g. Bab, Chapter, Vol, 第几章),
    and formats it in a beautiful zero-padded style (e.g., '01. Title Name', 'V2-01. Title Name').
    """
    import re
    t = title.strip()
    
    # 1. Clean out common brackets, quotes, braces at the edges
    t = re.sub(r'^[\'"“«「\[\(\s]+', '', t)
    t = re.sub(r'[\'"”»」\]\)\s]+$', '', t)
    
    # 2. Repeatedly strip common prefixes (nested loop for safety)
    while True:
        prev = t
        # Strip existing volume-aware prefixes like V1-098. or V2. or v1_99:
        t = re.sub(r'(?i)^v\d+[-_]?\d*\s*[\.\-:：~\s]*', '', t).strip()
        # Strip "Chapter X", "Bab X", "Vol X", "Ch X", "Volume X" (case insensitive)
        t = re.sub(r'(?i)^(chapter|bab|vol|volume|ch)\s*\d+\s*[\.\-:：~\s]*', '', t).strip()
        # Strip Chinese chapter prefixes: 第X章 or 第X话 or 第X节 or 第X回 or 第X卷
        t = re.sub(r'^第\s*\d+\s*[章节话回卷节]\s*[\.\-:：~\s]*', '', t).strip()
        # Strip leading numbers with dots, dashes, colons: e.g. "1. ", "01 - ", "12: "
        t = re.sub(r'^\d+\s*[\.\-:：~\s]+\s*', '', t).strip()
        # Strip just leading digits if they are separated by space
        t = re.sub(r'^\d+\s+', '', t).strip()
        
        if t == prev:
            break
            
    # 3. Clean up residual wrapping characters again
    t = re.sub(r'^[\'"“«「\[\(\s]+', '', t)
    t = re.sub(r'[\'"”»」\]\)\s]+$', '', t)

    # 4. Calculate dynamic padding width based on total number of chapters
    width = 2
    if total_chapters >= 1000:
        width = 4
    elif total_chapters >= 100:
        width = 3
        
    # Format
    padded = f"{order_num:0{width}d}"
    if volume_num is not None:
        # User Option A format: V2-01. Title
        if not t:
            return f"V{volume_num}-{padded}. Chapter {order_num}"
        return f"V{volume_num}-{padded}. {t}"
    
    # If the clean title is empty (e.g. original was just "Chapter 12"), fallback to "Chapter {order_num}"
    if not t:
        return f"{padded}. Chapter {order_num}"
    return f"{padded}. {t}"

class ImportURLRequest(BaseModel):
    url: str


class BatchTranslateRequest(BaseModel):
    chapter_ids: List[int]
    ai_extract: bool = True
    target_lang: Optional[str] = "Indonesian"
    overwrite: bool = True


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
    cover_image: Optional[str] = None
    original_title: Optional[str] = None
    genres: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None
    status_coo: Optional[str] = None
    synopsis: Optional[str] = None
    author: Optional[str] = None
    chapter_count: int
    created_at: Optional[str]
    last_read: Optional[str] = None
    last_read_id: Optional[int] = None
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
        bookmark = db.execute(bookmark_stmt).scalars().first()
        
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
            cover_image=t.cover_image,
            original_title=t.original_title,
            genres=t.genres,
            tags=t.tags,
            status=t.status,
            status_coo=t.status_coo,
            synopsis=t.synopsis,
            author=t.author,
            chapter_count=ch_count,
            created_at=str(t.created_at) if t.created_at else None,
            last_read=last_read_title,
            last_read_id=bookmark.chapter_id if bookmark else None,
            progress=progress
        ))
    return result


@router.get("/threads/active-batch")
def get_active_batch(db: Session = Depends(get_db)):
    """Get the currently active global batch translation progress if any."""
    from services.background_translator import active_batches
    if not active_batches:
        return {
            "active": False,
            "thread_id": None,
            "thread_title": "",
            "total": 0,
            "completed": 0,
            "current_chapter_id": None,
            "current_chapter_title": "",
            "failed_ids": []
        }
    
    thread_id = list(active_batches.keys())[0]
    batch = active_batches[thread_id]
    
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    thread_title = thread.title if thread else "Unknown Book"
    
    return {
        "active": True,
        "thread_id": thread_id,
        "thread_title": thread_title,
        "total": batch.total,
        "completed": batch.completed,
        "current_chapter_id": batch.current_chapter_id,
        "current_chapter_title": batch.current_chapter_title,
        "failed_ids": batch.failed_ids
    }


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

    # Get bookmark for this thread
    bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id)
    bookmark = db.execute(bookmark_stmt).scalars().first()

    return ThreadDetail(
        id=thread.id,
        title=thread.title,
        source_type=thread.source_type,
        source_url=thread.source_url,
        cover_image=thread.cover_image,
        original_title=thread.original_title,
        genres=thread.genres,
        tags=thread.tags,
        status=thread.status,
        status_coo=thread.status_coo,
        synopsis=thread.synopsis,
        author=thread.author,
        chapter_count=len(ch_out),
        created_at=str(thread.created_at) if thread.created_at else None,
        chapters=ch_out,
        last_read_id=bookmark.chapter_id if bookmark else None
    )


class ThreadCoverUpdate(BaseModel):
    cover_image: Optional[str] = None


@router.put("/threads/{thread_id}/cover")
def update_thread_cover(thread_id: int, payload: ThreadCoverUpdate, db: Session = Depends(get_db)):
    """Update cover image for a thread (Base64 or URL)."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
    
    thread.cover_image = payload.cover_image
    db.commit()
    return {"status": "success", "cover_image": thread.cover_image}


@router.get("/threads/{thread_id}/chapters/{chapter_id}", response_model=ChapterContent)
def get_chapter(thread_id: int, chapter_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Get single chapter with full content."""
    stmt = select(Chapter).where(Chapter.id == chapter_id, Chapter.thread_id == thread_id)
    chapter = db.execute(stmt).scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    # Update bookmark (Background history)
    bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id)
    bookmark = db.execute(bookmark_stmt).scalars().first()
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
    prefetch_on = gs.prefetch_enabled == 1 if gs else False

    if prefetch_on:
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
        
    from services.context_engine import ContextEngine
    chapter.content_translated = ContextEngine.strip_translator_notes(body.translated_text)
    db.commit()
    return {"status": "saved"}


@router.post("/threads/{thread_id}/translate-titles")
async def translate_titles(
    thread_id: int, 
    target_lang: str = "Indonesian", 
    repolish: bool = False,
    chapter_id: Optional[int] = None,
    start_number: Optional[int] = None,
    volume_mode: bool = Query(False, description="Enable Volume-aware numbering format"),
    auto_detect_volume: bool = Query(False, description="Auto-detect volume boundaries from raw title numbers"),
    start_volume: int = Query(1, description="Starting volume number if no previous volumes exist"),
    volume_boundaries: Optional[str] = Query(None, description="Comma-separated list of chapter numbers where a new volume begins"),
    volume_boundary_type: str = Query("raw", description="Boundary matching type: 'raw' or 'sequence'"),
    chapters_per_volume: Optional[int] = Query(None, description="Fixed number of chapters per volume"),
    db: Session = Depends(get_db)
):
    """Bulk translate or polish titles in a thread."""
    from services.ai_provider import AIProvider
    import re

    # Get server-side settings
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    lm_url = gs.lm_url if gs else "http://localhost:1234"
    polish_mode = gs.polish_mode if gs else "soft"
    polish_soft_limit = gs.polish_soft_limit if gs else 100

    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    
    if not thread:
        raise HTTPException(404, "Thread not found")

    # Unicode utility to detect Chinese chars
    def contains_chinese(text: str) -> bool:
        if not text:
            return False
        return any('\u4e00' <= char <= '\u9fff' for char in text)

    # Clean thread original title and translate thread synopsis/description if bulk polishing
    if not chapter_id:
        # A. Clean Original Title (ADR-020 Compliance)
        if thread.original_title and contains_chinese(thread.original_title):
            print(f"🔄 [ADR-020] Cleansing original title: {thread.original_title}")
            sys_prompt_clean = (
                "You are an expert Chinese web novel database assistant.\n"
                "Your task is to take a raw, messy Chinese novel title (which may contain extra words, descriptive text, "
                "parentheses, tags, or chapter details) and return ONLY the clean, official Chinese title of the novel.\n"
                "Rules:\n"
                "1. Strip all annotations, brackets like 【】, tags like (无女主) or (轻松) or (变百), and ads.\n"
                "2. Respond with ONLY the cleaned Chinese title characters. Do not include any greeting, markdown, note, or translation.\n"
                "3. If the input is already clean or contains English, return it clean without explaining.\n"
                "Example Input: 我怎么可能是圣女？（无女主，变百，轻松）\n"
                "Example Output: 我怎么可能是圣女？"
            )
            user_prompt_clean = f"Please clean this title: {thread.original_title}"
            try:
                cleaned_title = await AIProvider.generate_batch(sys_prompt_clean, user_prompt_clean, base_url=lm_url)
                cleaned_title = cleaned_title.strip()
                if cleaned_title and len(cleaned_title) < 200:
                    print(f"✅ Cleaned original title to: {cleaned_title}")
                    thread.original_title = cleaned_title
            except Exception as e:
                print(f"⚠️ Failed to clean original_title in translate_titles: {e}")

        # B. Translate Synopsis if still in Chinese
        if thread.synopsis and contains_chinese(thread.synopsis):
            print(f"🔄 Translating Chinese synopsis/description...")
            sys_prompt_syn = (
                f"You are a professional literary translator specializing in {target_lang}. "
                "Translate the following novel synopsis/description accurately and elegantly. "
                "Ensure the translation is natural and highly readable, retaining the original meaning and tone."
            )
            user_prompt_syn = thread.synopsis
            try:
                translated_syn = await AIProvider.generate_batch(sys_prompt_syn, user_prompt_syn, base_url=lm_url)
                translated_syn = translated_syn.strip()
                if translated_syn:
                    print(f"✅ Successfully translated synopsis.")
                    thread.synopsis = translated_syn
            except Exception as e:
                print(f"⚠️ Failed to translate synopsis in translate_titles: {e}")
                
        db.commit()

    # Load all chapters for accurate sequence analysis to compute metrics across the entire thread
    ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order)
    all_chapters = db.execute(ch_stmt).scalars().all()

    if not all_chapters:
        return {"count": 0}

    # Filter chapters if polishing a single chapter
    if chapter_id:
        chapters = [c for c in all_chapters if c.id == chapter_id]
    else:
        chapters = all_chapters

    if not chapters:
        return {"count": 0}

    # Count total chapters in the thread for padding width calculation
    total_chapters = len(all_chapters)

    start_num_offset = start_number

    chapter_metrics = {}
    if volume_mode:
        
        # Parse volume boundaries
        vol_boundaries = set()
        if volume_boundaries:
            try:
                vol_boundaries = {int(x.strip()) for x in volume_boundaries.split(",") if x.strip()}
            except Exception:
                pass
        
        current_vol = start_volume
        current_ch = start_num_offset if start_num_offset is not None else 1
        prev_raw_num = 0
        volume_just_incremented = False
        
        for c in all_chapters:
            if not c.title_original:
                chapter_metrics[c.id] = (current_vol, current_ch)
                current_ch += 1
                volume_just_incremented = False
                continue
                
            raw_num = 0
            match = re.search(r'(?i)(?:chapter|bab|vol|volume|ch|第)\s*(\d+)', c.title_original)
            if match:
                raw_num = int(match.group(1))
            else:
                match = re.search(r'\d+', c.title_original)
                if match:
                    raw_num = int(match.group(0))
            
            # Prologue/Epilogue detection
            is_prologue = False
            title_lower = c.title_original.lower()
            prologue_keywords = ["序章", "楔子", "序言", "引子", "prologue", "prelude"]
            if any(kw in title_lower for kw in prologue_keywords):
                is_prologue = True
                    
            # Boundary detection
            is_boundary = False
            if vol_boundaries:
                if volume_boundary_type == "sequence":
                    if (c.order + 1) in vol_boundaries:
                        is_boundary = True
                else: # default to "raw"
                    if raw_num > 0 and raw_num in vol_boundaries:
                        is_boundary = True
                        
            if chapters_per_volume and chapters_per_volume > 0:
                if c.order > 0 and c.order % chapters_per_volume == 0:
                    is_boundary = True
                    
            # Transition application with guard
            if is_boundary:
                current_vol += 1
                current_ch = 1
                volume_just_incremented = True
            elif is_prologue and c.order > 0:
                current_vol += 1
                current_ch = 0
                volume_just_incremented = True
            elif auto_detect_volume and prev_raw_num > 0 and raw_num > 0 and raw_num < prev_raw_num and raw_num < 10:
                if not volume_just_incremented:
                    current_vol += 1
                    current_ch = raw_num
                    volume_just_incremented = True
                else:
                    current_ch = raw_num
                    volume_just_incremented = False
            else:
                volume_just_incremented = False
                
            chapter_metrics[c.id] = (current_vol, current_ch)
            current_ch += 1
            if raw_num > 0:
                prev_raw_num = raw_num
    else:
        detected_start = 1
        first_ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order).limit(1)
        first_ch = db.execute(first_ch_stmt).scalar_one_or_none()
        if first_ch and first_ch.title_original:
            match = re.search(r'(?i)(?:chapter|bab|vol|volume|ch|第)\s*(\d+)', first_ch.title_original)
            if match:
                detected_start = int(match.group(1))
            else:
                match = re.search(r'\d+', first_ch.title_original)
                if match:
                    detected_start = int(match.group(0))
        start_num_offset = start_num_offset if start_num_offset is not None else detected_start
        max_chapter_num = start_num_offset + total_chapters - 1

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

    # If soft load mode is active, limit the number of chapter titles to process
    if not chapter_id and polish_mode == "soft":
        print(f"ℹ️ [SOFT LOAD] Limiting title processing to {polish_soft_limit} items.")
        titles_to_process = titles_to_process[:polish_soft_limit]
        indices = indices[:polish_soft_limit]

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
                                target_ch = chapters[ch_idx]
                                if volume_mode:
                                    v_num, c_num = chapter_metrics.get(target_ch.id, (start_volume, 1))
                                    formatted_title = clean_and_format_chapter_title(
                                        translated_title,
                                        c_num,
                                        total_chapters,
                                        volume_num=v_num
                                    )
                                else:
                                    order_num = start_num_offset + target_ch.order
                                    formatted_title = clean_and_format_chapter_title(
                                        translated_title,
                                        order_num,
                                        max_chapter_num
                                    )
                                target_ch.title_translated = formatted_title
                                total_count += 1
                    except Exception as e:
                        print(f"⚠️ Skip line '{line}': {e}")
            
            db.commit() # Commit each chunk
        except Exception as e:
            print(f"❌ Batch Error at chunk {start_idx}: {e}")
            # Continue to next chunk if one fails? Or raise?
            # Let's raise to alert user if the connection is dead
            raise HTTPException(500, f"AI Error at chunk {start_idx}: {str(e)}")

    # Sweep and apply volume/sequential formatting to ALL chapters in the thread that have translated titles
    # This guarantees that pre-existing translations or translations past the soft limit still get correctly formatted!
    for target_ch in all_chapters:
        if target_ch.title_translated:
            if volume_mode:
                v_num, c_num = chapter_metrics.get(target_ch.id, (start_volume, 1))
                formatted_title = clean_and_format_chapter_title(
                    target_ch.title_translated,
                    c_num,
                    total_chapters,
                    volume_num=v_num
                )
            else:
                order_num = start_num_offset + target_ch.order
                formatted_title = clean_and_format_chapter_title(
                    target_ch.title_translated,
                    order_num,
                    max_chapter_num
                )
            target_ch.title_translated = formatted_title
    
    db.commit()

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
@router.post("/threads/{thread_id}/batch-translate")
async def batch_translate(
    thread_id: int, 
    req: BatchTranslateRequest,
    db: Session = Depends(get_db)
):
    """Trigger sequential, GPU-friendly batch translation for multiple chapters."""
    from database import LorebookEntry
    from services.background_translator import BackgroundTranslator
    
    # 1. Check thread existence
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    # 2. Check Lorebook count (Smart Logic)
    lore_count_stmt = select(func.count(LorebookEntry.id)).where(LorebookEntry.thread_id == thread_id)
    lore_count = db.execute(lore_count_stmt).scalar() or 0
    
    # Get global settings
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    lm_url = gs.lm_url if gs else "http://localhost:1234"
    model = gs.lm_model if gs else None
    target_lang = req.target_lang or (gs.target_language if gs else "Indonesian")

    # 3. Start sequential queue
    await BackgroundTranslator.start_batch(
        thread_id=thread_id,
        chapter_ids=req.chapter_ids,
        target_lang=target_lang,
        model=model,
        lm_url=lm_url,
        force_extract=req.ai_extract,
        force_overwrite=req.overwrite
    )

    return {
        "status": "started",
        "batch_size": len(req.chapter_ids),
        "lore_count": lore_count,
        "recommend_extract": lore_count < 40
    }



@router.get("/threads/{thread_id}/batch-status")
def get_batch_status(thread_id: int):
    """Get the active stateful batch translation progress for a specific thread."""
    from services.background_translator import active_batches
    batch = active_batches.get(thread_id)
    if not batch:
        return {
            "active": False,
            "total": 0,
            "completed": 0,
            "current_chapter_id": None,
            "current_chapter_title": "",
            "failed_ids": []
        }
    return {
        "active": True,
        "total": batch.total,
        "completed": batch.completed,
        "current_chapter_id": batch.current_chapter_id,
        "current_chapter_title": batch.current_chapter_title,
        "failed_ids": batch.failed_ids
    }


@router.post("/threads/{thread_id}/batch-stop")
async def stop_batch_translation(thread_id: int):
    """Gracefully cancel and stop active batch translation queue."""
    from services.background_translator import BackgroundTranslator
    await BackgroundTranslator.stop_batch(thread_id)
    return {"status": "stopped"}


class ScrapeMetadataRequest(BaseModel):
    original_title: Optional[str] = None
    include_cover: bool = True
    search_by: Optional[str] = "original"  # "original" or "translated"
    source: Optional[str] = "novelupdates"   # "novelupdates" or "sfacg"


@router.post("/threads/{thread_id}/scrape_metadata")
async def scrape_metadata(
    thread_id: int,
    req: ScrapeMetadataRequest,
    db: Session = Depends(get_db)
):
    """Scrape metadata from Novel Updates or SFACG directly."""
    import urllib.parse
    import httpx
    import re
    from bs4 import BeautifulSoup
    from services.ai_provider import AIProvider
    
    # 1. Fetch thread
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    # Check if SFACG direct scraping is needed
    is_sfacg = (req.source == "sfacg") or (req.original_title and "sfacg.com" in req.original_title) or (thread.source_url and "sfacg.com" in thread.source_url)
    
    if is_sfacg:
        from curl_cffi.requests import AsyncSession
        sfacg_url = req.original_title or thread.source_url or ""
        
        # Check if sfacg_url is a direct URL or just ID
        if sfacg_url.isdigit():
            sfacg_url = f"https://book.sfacg.com/Novel/{sfacg_url}/"
        elif not sfacg_url.startswith(("http://", "https://")):
            # Fallback if messy input
            num_match = re.search(r'(\d+)', sfacg_url)
            if num_match:
                sfacg_url = f"https://book.sfacg.com/Novel/{num_match.group(1)}/"
            else:
                raise HTTPException(400, f"Invalid SFACG URL or novel ID: {sfacg_url}")
                
        # Parse novel ID for normalization
        novel_id = None
        id_match = re.search(r'/Novel/(\d+)', sfacg_url, re.IGNORECASE)
        if not id_match:
            id_match = re.search(r'/b/(\d+)', sfacg_url, re.IGNORECASE)
        if id_match:
            novel_id = id_match.group(1)
            
        target_url = f"https://book.sfacg.com/Novel/{novel_id}/" if novel_id else sfacg_url
        print(f"🍍 Scraping SFACG directly: {target_url}")
        
        sfacg_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://book.sfacg.com/"
        }
        
        try:
            async with AsyncSession() as client:
                resp = await client.get(target_url, headers=sfacg_headers, impersonate="chrome110", timeout=15.0, verify=False)
                if resp.status_code != 200:
                    raise HTTPException(resp.status_code, f"Failed to retrieve SFACG page (status {resp.status_code}).")
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 1. Title (Mandarin Hanzi)
                title_el = soup.select_one(".d-summary .title") or soup.select_one(".d-normal-banner .title") or soup.select_one(".novel-info .title") or soup.select_one("h1")
                title = title_el.text.strip() if title_el else thread.title or "Untitled SFACG Novel"
                
                # 2. Synopsis
                introduce_el = soup.select_one(".d-summary .introduce") or soup.select_one(".introduce") or soup.select_one(".novel-intro")
                synopsis = introduce_el.text.strip() if introduce_el else ""
                
                # 3. Genres
                genre_links = soup.select(".tag-list .tag a") or soup.select(".previous-chapter .tag-list .tag a") or soup.select(".novel-tags a")
                genres_list = [a.text.strip() for a in genre_links if a.text.strip()]
                genres_str = ", ".join(genres_list) if genres_list else ""
                
                # 4. Cover Image
                cover_el = soup.select_one(".d-normal-banner .summary-pic img") or soup.select_one(".summary-pic img") or soup.select_one(".novel-cover img")
                cover_url = None
                if cover_el:
                    cover_url = cover_el.get("src", "")
                    if cover_url and cover_url.startswith("//"):
                        cover_url = "https:" + cover_url
                        
                # 5. Author
                author_el = soup.select_one(".author-name") or soup.select_one(".author-info") or soup.select_one("a[href*='/author/']") or soup.select_one(".novel-author") or soup.select_one("#showauthors")
                author = author_el.text.replace("作者：", "").replace("作者:", "").strip() if author_el else ""

                # Update Thread in DB
                thread.original_title = title  # Keep raw Chinese character title
                thread.title = title           # Set title to Chinese title, user can AI polish later
                if genres_str:
                    thread.genres = genres_str
                if synopsis:
                    thread.synopsis = synopsis
                if req.include_cover and cover_url:
                    thread.cover_image = cover_url
                if author:
                    thread.author = author
                    
                db.commit()
                
                return {
                    "success": True,
                    "title": title,
                    "original_title": title,
                    "author": author,
                    "genres": genres_str,
                    "tags": "",
                    "synopsis": synopsis,
                    "status": "Ongoing",
                    "status_coo": "Ongoing",
                    "cover_image": cover_url
                }
        except Exception as e:
            print(f"❌ SFACG Direct scraping error: {e}")
            raise HTTPException(500, f"Error scraping SFACG metadata: {str(e)}")

    # Get server-side settings for LM Studio base_url
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    lm_url = gs.lm_url if gs else "http://localhost:1234"
    
    if req.search_by == "translated":
        title_to_clean = req.original_title or thread.title or ""
    else:
        title_to_clean = req.original_title or thread.original_title or thread.title or ""
    
    # 2. AI original title cleansing
    cleaned_title = title_to_clean
    if title_to_clean:
        # Check if contains Chinese characters or other noise
        # Or simply run through LLM to isolate clean core title
        sys_prompt = (
            "You are an expert Chinese web novel database assistant.\n"
            "Your task is to take a raw, messy Chinese novel title (which may contain extra words, descriptive text, "
            "parentheses, tags, or chapter details) and return ONLY the clean, official Chinese title of the novel.\n"
            "Rules:\n"
            "1. Strip all annotations, brackets like 【】, tags like (无女主) or (轻松) or (变百), and ads.\n"
            "2. Respond with ONLY the cleaned Chinese title characters. Do not include any greeting, markdown, note, or translation.\n"
            "3. If the input is already clean or contains English, return it clean without explaining.\n"
            "Example Input: 我怎么可能是圣女？（无女主，变百，轻松）\n"
            "Example Output: 我怎么可能是圣女？"
        )
        user_prompt = f"Please clean this title: {title_to_clean}"
        try:
            cleaned_title = await AIProvider.generate_batch(sys_prompt, user_prompt, base_url=lm_url)
            cleaned_title = cleaned_title.strip()
            # If the model fails or returns empty, fallback to original
            if not cleaned_title or len(cleaned_title) > 200:
                cleaned_title = title_to_clean
        except Exception as e:
            print(f"⚠️ Failed to clean title using AI: {e}. Falling back to original.")
            cleaned_title = title_to_clean
            
    # 3. Novel Updates Search Scraping (with Yahoo Search first & fallback to direct NU search)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/"
    }
    
    # Matching normalization functions for robust matching
    def clean_for_match(s: str) -> str:
        if not s:
            return ""
        return "".join(c for c in s.lower() if c.isalnum() or '\u4e00' <= c <= '\u9fff')

    def is_match(query_title: str, orig_title: str, official: str, assoc_names: list[str]) -> bool:
        q_clean = clean_for_match(query_title)
        o_clean = clean_for_match(orig_title)
        off_clean = clean_for_match(official)
        
        # Helper to check matching character overlap threshold
        def overlap_match(s1: str, s2: str) -> bool:
            if not s1 or not s2:
                return False
            if s1 in s2 or s2 in s1:
                return True
            # Character overlap for Chinese characters
            cn1 = [c for c in s1 if '\u4e00' <= c <= '\u9fff']
            if cn1:
                cn2 = [c for c in s2 if '\u4e00' <= c <= '\u9fff']
                intersect = set(cn1).intersection(set(cn2))
                if len(cn1) > 0 and len(intersect) / len(cn1) >= 0.5:
                    return True
            return False

        # Check official title
        if overlap_match(q_clean, off_clean) or (o_clean and overlap_match(o_clean, off_clean)):
            return True
        
        # Check associated names
        for assoc in assoc_names:
            assoc_clean = clean_for_match(assoc)
            if overlap_match(q_clean, assoc_clean) or (o_clean and overlap_match(o_clean, assoc_clean)):
                return True
                
        return False

    candidates = [] # list of URLs

    # Try Yahoo Search first
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession() as client:
            search_query = f"{cleaned_title} site:novelupdates.com"
            encoded_query = urllib.parse.quote(search_query)
            yahoo_url = f"https://search.yahoo.com/search?p={encoded_query}"
            
            print(f"🔍 Searching Yahoo Search: {yahoo_url}")
            resp = await client.get(yahoo_url, headers=headers, impersonate="chrome110", timeout=12.0, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    # Check if direct url in href or in Yahoo redirect parameter RU
                    target_url = None
                    if "novelupdates.com/series/" in href:
                        target_url = href
                    elif "r.search.yahoo.com" in href and "RU=" in href:
                        # Extract RU parameter
                        try:
                            ru_part = href.split("RU=", 1)[1].split("/", 1)[0]
                            # Make sure we decode properly
                            decoded = urllib.parse.unquote(href.split("RU=", 1)[1].split("/RK=", 1)[0])
                            if "novelupdates.com/series/" in decoded:
                                target_url = decoded
                        except Exception:
                            pass
                    
                    if target_url and "/series/" in target_url:
                        # Clean direct link to avoid any extra yahoo query params
                        clean_url = target_url.split("?")[0].split("&")[0].split("/RS=")[0]
                        if clean_url not in candidates:
                            candidates.append(clean_url)
    except Exception as e:
        print(f"⚠️ Yahoo Search failed or timed out: {e}")

    # Fallback to direct Novel Updates search if no candidates from Yahoo Search
    if not candidates:
        try:
            encoded_title = urllib.parse.quote(cleaned_title)
            search_url = f"https://www.novelupdates.com/?s={encoded_title}"
            print(f"🔍 Falling back to direct Novel Updates Search: {search_url}")
            from curl_cffi.requests import AsyncSession
            async with AsyncSession() as client:
                resp = await client.get(search_url, headers=headers, impersonate="chrome110", timeout=12.0)
                if resp.status_code == 200:
                    final_url = str(resp.url)
                    if "/series/" in final_url:
                        candidates.append(final_url.split("?")[0])
                    else:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        search_results = soup.select(".search_title a")
                        if not search_results:
                            search_results = soup.select(".w-blog-entry-title a")
                        if not search_results:
                            search_results = [a for a in soup.find_all('a') if a.get('href') and "/series/" in a.get('href')]
                        
                        for sr in search_results:
                            href = sr.get('href', '').split("?")[0]
                            if href and href not in candidates:
                                candidates.append(href)
        except Exception as e:
            print(f"⚠️ Direct Novel Updates search failed: {e}")

    if not candidates:
        raise HTTPException(404, f"No series found on Novel Updates for '{cleaned_title}'")

    # Iterate candidates, fetch details, cross-check associated names
    print(f"📋 Found {len(candidates)} series candidates. Resolving and cross-checking...")
    
    matched_detail_url = None
    detail_html = None
    first_candidate_html = None
    first_candidate_url = candidates[0]
    
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession() as client:
            for cand_url in candidates[:5]: # Check top 5 matches
                print(f"🕵️ Checking candidate: {cand_url}")
                try:
                    resp = await client.get(cand_url, headers=headers, impersonate="chrome110", timeout=10.0)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        
                        # Official Title
                        official_title = None
                        title_el = soup.select_one(".seriestitlenu") or soup.select_one(".seriestitle span") or soup.select_one(".seriestitle")
                        if title_el:
                            official_title = title_el.text.strip()
                            
                        # Associated Names
                        associated_names = []
                        assoc_el = soup.select_one("#editassociated")
                        if assoc_el:
                            # Replace breaks with newlines to split names cleanly
                            html_content = str(assoc_el)
                            html_content = html_content.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
                            clean_soup = BeautifulSoup(html_content, 'html.parser')
                            associated_names = [line.strip() for line in clean_soup.text.split("\n") if line.strip()]
                            
                        print(f"   Official title: {official_title}")
                        print(f"   Associated names: {associated_names}")
                        
                        # Save first candidate details in case no exact match is verified
                        if not first_candidate_html:
                            first_candidate_html = resp.text
                            first_candidate_url = cand_url
                            
                        # Verify match
                        if is_match(cleaned_title, thread.original_title, official_title or "", associated_names):
                            print(f"🎯 Verified Match found: {cand_url}!")
                            matched_detail_url = cand_url
                            detail_html = resp.text
                            break
                except Exception as ex:
                    print(f"   ⚠️ Error checking candidate {cand_url}: {ex}")
                    continue
    except Exception as e:
        print(f"⚠️ Resolution loop failed: {e}")

    # Fallback to the first candidate if no verified match was found
    if not matched_detail_url:
        if first_candidate_html:
            print(f"⚠️ No exact match verified. Falling back to the first candidate: {first_candidate_url}")
            matched_detail_url = first_candidate_url
            detail_html = first_candidate_html
        else:
            raise HTTPException(404, f"Failed to retrieve detail pages for matched candidates.")

    detail_url = matched_detail_url

    # 4. Scrape Detail Page HTML
    soup = BeautifulSoup(detail_html, 'html.parser')
    
    # Official Title
    official_title = None
    title_el = soup.select_one(".seriestitlenu") or soup.select_one(".seriestitle span") or soup.select_one(".seriestitle")
    if title_el:
        official_title = title_el.text.strip()
        
    # Genres
    genres_list = [a.text.strip() for a in soup.select("#seriesgenre a")]
    genres_str = ", ".join(genres_list) if genres_list else None
    
    # Tags
    tags_list = [a.text.strip() for a in soup.select("#showtags a") or soup.select("#seriestags a")]
    tags_str = ", ".join(tags_list) if tags_list else None
    
    # Synopsis / Description
    synopsis_str = None
    synopsis_el = soup.select_one("#editdescription")
    if synopsis_el:
        synopsis_str = synopsis_el.text.strip()
        
    # Author
    author_str = None
    author_el = soup.select_one("#showauthors") or soup.select_one(".author") or soup.select_one("a[href*='/author/']")
    if author_el:
        author_str = author_el.text.strip()
        
    # COO & Translation Status
    status_coo_str = None
    coo_el = soup.select_one("#editstatus")
    if coo_el:
        lines = [line.replace("\r", "").strip() for line in coo_el.text.split("\n")]
        status_coo_str = ", ".join([l for l in lines if l])
        
    status_str = None
    translated_el = soup.select_one("#showtranslated") or soup.select_one("#edittranslated")
    if translated_el:
        status_str = f"Completely Translated: {translated_el.text.strip()}"
                    
    # Cover Image
    cover_img_url = None
    if req.include_cover:
        img_el = soup.select_one(".seriesimg img")
        if img_el and img_el.get('src'):
            cover_img_url = img_el['src']
            if not cover_img_url.startswith("http"):
                cover_img_url = "https:" + cover_img_url if cover_img_url.startswith("//") else cover_img_url
    
    # 5. Persist to DB
    thread.original_title = cleaned_title
    if official_title:
        thread.title = official_title
    if genres_str:
        thread.genres = genres_str
    if tags_str:
        thread.tags = tags_str
    if synopsis_str:
        thread.synopsis = synopsis_str
    if status_coo_str:
        thread.status_coo = status_coo_str
    if status_str:
        thread.status = status_str
    if cover_img_url:
        thread.cover_image = cover_img_url
    if author_str:
        thread.author = author_str
        
    db.commit()
    
    return {
        "success": True,
        "original_title": cleaned_title,
        "title": official_title or thread.title,
        "author": author_str,
        "genres": genres_str,
        "tags": tags_str,
        "status": status_str,
        "status_coo": status_coo_str,
        "synopsis": synopsis_str,
        "cover_image": cover_img_url,
        "detail_url": detail_url
    }

