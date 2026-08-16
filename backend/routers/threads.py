"""
Thread & Chapter management endpoints.
GET /api/threads — list all
GET /api/threads/{id} — detail + chapters
DELETE /api/threads/{id} — delete thread + cascade
GET /api/threads/{id}/chapters/{chapter_id} — single chapter content
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Optional

from database import get_db, Thread, Chapter, TranslationSegment, GlobalSetting, UserBookmark
from services.cleaner_tools import CleanerTools
from services.hallucination_detector import HallucinationDetector

router = APIRouter(prefix="/api", tags=["Threads"])


class ChapterOut(BaseModel):
    id: int
    order: int
    title_original: Optional[str]
    title_translated: Optional[str]
    word_count: int
    has_translation: bool
    translation_status: str
    is_bookmarked: bool = False
    fidelity_warning: Optional[str] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


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
    style_guide: Optional[str] = None
    chapters: List[ChapterOut]


class TranslationSegmentOut(BaseModel):
    id: int
    order: int
    original_text: Optional[str]
    translated_text: Optional[str]
    display_mode: str

    model_config = ConfigDict(from_attributes=True)


class ChapterContent(BaseModel):
    id: int
    order: int
    title_original: Optional[str]
    title_translated: Optional[str]
    content_original: Optional[str]
    content_translated: Optional[str]
    translation_status: Optional[str]
    source_url: Optional[str] = None
    scroll_progress: float = 0.0
    is_bookmarked: bool = False
    fidelity_warning: Optional[str] = None
    segments: List[TranslationSegmentOut] = []

class HallucinationMatchOut(BaseModel):
    token: str
    count: int
    start_index: int
    end_index: int
    snippet: str


class ChapterHallucinationAuditOut(BaseModel):
    chapter_id: int
    chapter_order: int
    chapter_title: Optional[str]
    status: str
    has_repetition: bool
    match_count: int
    repetition_matches: List[HallucinationMatchOut] = []


class ThreadHallucinationAuditOut(BaseModel):
    thread_id: int
    checked_chapters: int
    flagged_chapters: int
    repetition_threshold: int
    chapters: List[ChapterHallucinationAuditOut]


class CleanerToolResponse(BaseModel):
    thread_id: int
    tool: str
    chapters_scanned: int
    chapters_deleted: int
    chapters_updated: int
    lines_removed: int


class CleanupPreviewResponse(BaseModel):
    chapters_scanned: int
    chapters_deleted: int
    chapters_updated: int
    lines_removed: int
    deleted_chapter_ids: List[int]
    cleaned_text: str

class ThreadUpdatePayload(BaseModel):
    title: str | None = None
    original_title: str | None = None
    genres: str | None = None
    tags: str | None = None
    author: str | None = None
    synopsis: str | None = None

@router.get("/threads", response_model=List[ThreadItemOut])
def list_threads(db: Session = Depends(get_db)):
    """List all threads with reading progress (batch optimized)."""
    threads = db.execute(select(Thread).order_by(Thread.id.desc())).scalars().all()
    if not threads:
        return []
    
    # Batch fetch chapter counts (1 query)
    ch_counts_stmt = select(Chapter.thread_id, func.count(Chapter.id)).group_by(Chapter.thread_id)
    ch_counts = dict(db.execute(ch_counts_stmt).all())
    
    # Batch fetch bookmarks with referenced chapter metadata (1 query)
    bookmarks_stmt = (
        select(
            UserBookmark.thread_id,
            UserBookmark.chapter_id,
            Chapter.title_translated,
            Chapter.title_original,
            Chapter.order
        )
        .join(Chapter, UserBookmark.chapter_id == Chapter.id)
    )
    bookmark_rows = db.execute(bookmarks_stmt).all()
    bookmark_map = {row[0]: (row[1], row[2] or row[3], row[4]) for row in bookmark_rows}
    
    result = []
    for t in threads:
        ch_count = ch_counts.get(t.id, 0)
        bookmark_info = bookmark_map.get(t.id)
        
        last_read_title = None
        last_read_id = None
        progress = 0
        
        if bookmark_info:
            last_read_id = bookmark_info[0]
            last_read_title = bookmark_info[1]
            last_order = bookmark_info[2]
            if ch_count > 0:
                progress = int(((last_order + 1) / ch_count) * 100)
        
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
            last_read_id=last_read_id,
            progress=progress
        ))
    return result


@router.patch("/threads/{thread_id}")
def update_thread(thread_id: int, payload: ThreadUpdatePayload, db: Session = Depends(get_db)):
    """Edit thread metadata: title, genres, tags, author, synopsis."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    if payload.title is not None:
        thread.title = payload.title
    if payload.original_title is not None:
        thread.original_title = payload.original_title
    if payload.genres is not None:
        thread.genres = payload.genres
    if payload.tags is not None:
        thread.tags = payload.tags
    if payload.author is not None:
        thread.author = payload.author
    if payload.synopsis is not None:
        thread.synopsis = payload.synopsis
    db.commit()
    return {"status": "updated", "thread_id": thread_id}


@router.get("/threads/{thread_id}/context")
def get_thread_context(thread_id: int, db: Session = Depends(get_db)):
    """Get thread-level context (thread_context + style_guide) for Context Library page."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
    return {
        "thread_context": thread.thread_context or "",
        "style_guide": thread.style_guide or "",
        "genres": thread.genres or "",
        "tags": thread.tags or "",
    }


@router.post("/threads/{thread_id}/context")
def save_thread_context(thread_id: int, body: dict, db: Session = Depends(get_db)):
    """Save thread-level context."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
    if "context" in body:
        thread.thread_context = body["context"]
    if "style_guide" in body:
        thread.style_guide = body["style_guide"]
    db.commit()
    return {"status": "saved"}


@router.get("/threads/active-batch")
def get_active_batch(db: Session = Depends(get_db)):
    """Get the currently active global batch translation progress if any."""
    from services.background_translator import active_batches
    
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    from services.ai.secrets import get_key_stats
    stats = get_key_stats(gs.llm_provider if gs else "lm_studio", gs)
    
    if not active_batches:
        return {
            "active": False,
            "thread_id": None,
            "thread_title": "",
            "total": 0,
            "completed": 0,
            "current_chapter_id": None,
            "current_chapter_title": "",
            "failed_ids": [],
            "quota_exhausted": False,
            "total_keys": stats["total"],
            "exhausted_keys": stats["exhausted"],
            "queue_count": 0,
            "is_waiting": False
        }
    
    # Prioritize showing the currently running batch (not waiting)
    active_thread_id = None
    for tid, b in list(active_batches.items()):
        if getattr(b, "is_waiting", False) is False:
            active_thread_id = tid
            break
            
    if active_thread_id is None:
        active_thread_id = list(active_batches.keys())[0]
        
    batch = active_batches[active_thread_id]
    
    stmt = select(Thread).where(Thread.id == active_thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    thread_title = thread.title if thread else "Unknown Book"
    
    return {
        "active": True,
        "thread_id": active_thread_id,
        "thread_title": thread_title,
        "total": batch.total,
        "completed": batch.completed,
        "current_chapter_id": batch.current_chapter_id,
        "current_chapter_title": batch.current_chapter_title,
        "failed_ids": batch.failed_ids,
        "quota_exhausted": getattr(batch, "quota_exhausted", False),
        "total_keys": stats["total"],
        "exhausted_keys": stats["exhausted"],
        "queue_count": len(active_batches) - 1,
        "is_waiting": getattr(batch, "is_waiting", False)
    }


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
def get_thread(thread_id: int, db: Session = Depends(get_db)):
    """Get thread with chapter list."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    
    if not thread:
        raise HTTPException(404, "Thread not found")

    ch_stmt = (
        select(
            Chapter.id,
            Chapter.order,
            Chapter.title_original,
            Chapter.title_translated,
            func.length(func.coalesce(Chapter.content_original, "")),
            (Chapter.content_translated.is_not(None) & (Chapter.content_translated != "")),
            Chapter.translation_status,
            Chapter.is_bookmarked,
            Chapter.fidelity_warning,
            Chapter.source_url
        )
        .where(Chapter.thread_id == thread_id)
        .order_by(Chapter.order)
    )
    ch_rows = db.execute(ch_stmt).all()

    ch_out = [
        ChapterOut(
            id=row[0],
            order=row[1],
            title_original=row[2],
            title_translated=row[3],
            word_count=row[4],
            has_translation=bool(row[5]),
            translation_status=row[6],
            is_bookmarked=bool(row[7]),
            fidelity_warning=row[8],
            source_url=row[9]
        )
        for row in ch_rows
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


@router.get("/threads/{thread_id}/hallucination-check", response_model=ThreadHallucinationAuditOut)
def check_thread_hallucination(thread_id: int, db: Session = Depends(get_db)):
    """Audit translated chapters for 10x consecutive repeated-word hallucinations."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()

    if not thread:
        raise HTTPException(404, "Thread not found")

    chapters_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order)
    chapters = db.execute(chapters_stmt).scalars().all()

    threshold = 10
    audits: list[ChapterHallucinationAuditOut] = []
    flagged_count = 0

    for chapter in chapters:
        translated = (chapter.content_translated or "").strip()
        if not translated:
            audits.append(ChapterHallucinationAuditOut(
                chapter_id=chapter.id,
                chapter_order=chapter.order,
                chapter_title=chapter.title_translated or chapter.title_original,
                status="no_translation",
                has_repetition=False,
                match_count=0,
                repetition_matches=[],
            ))
            continue

        audit = HallucinationDetector.summarize_text_audit(translated, threshold=threshold)
        if audit["has_repetition"]:
            flagged_count += 1

        audits.append(ChapterHallucinationAuditOut(
            chapter_id=chapter.id,
            chapter_order=chapter.order,
            chapter_title=chapter.title_translated or chapter.title_original,
            status="flagged" if audit["has_repetition"] else "clean",
            has_repetition=audit["has_repetition"],
            match_count=len(audit["repetition_matches"]),
            repetition_matches=[HallucinationMatchOut(**match) for match in audit["repetition_matches"]],
        ))

    return ThreadHallucinationAuditOut(
        thread_id=thread_id,
        checked_chapters=len(audits),
        flagged_chapters=flagged_count,
        repetition_threshold=threshold,
        chapters=audits,
    )


@router.post("/threads/{thread_id}/txt-cleaner", response_model=CleanerToolResponse)
def run_txt_cleaner(thread_id: int, db: Session = Depends(get_db)):
    """Rule-based cleaner for chapter text garbage such as ads, web spam, and noisy lines."""
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    summary = CleanerTools.run_txt_cleaner(thread)
    db.commit()

    return CleanerToolResponse(
        thread_id=thread_id,
        tool="txt_cleaner",
        chapters_scanned=summary.chapters_scanned,
        chapters_deleted=summary.chapters_deleted,
        chapters_updated=summary.chapters_updated,
        lines_removed=summary.lines_removed,
    )


@router.post("/threads/{thread_id}/epub-cleaner", response_model=CleanerToolResponse)
def run_epub_cleaner(thread_id: int, db: Session = Depends(get_db)):
    """Rule-based cleaner for EPUB-imported false chapters such as TOC, ads, and micro-junk pages."""
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    summary = CleanerTools.run_epub_cleaner(thread)
    for chapter in list(thread.chapters):
        if chapter.id in summary.deleted_chapter_ids:
            db.delete(chapter)

    db.commit()

    return CleanerToolResponse(
        thread_id=thread_id,
        tool="epub_cleaner",
        chapters_scanned=summary.chapters_scanned,
        chapters_deleted=summary.chapters_deleted,
        chapters_updated=summary.chapters_updated,
        lines_removed=summary.lines_removed,
    )


@router.post("/threads/{thread_id}/cleanup-preview", response_model=CleanupPreviewResponse)
def preview_cleanup(thread_id: int, db: Session = Depends(get_db)):
    """Generate a cleanup preview without mutating the database."""
    import io
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    # Work with copies of chapter data to avoid mutating ORM objects
    chapters_sorted = sorted(thread.chapters, key=lambda c: c.order)
    chapter_copies = []
    for ch in chapters_sorted:
        chapter_copies.append({
            "id": ch.id,
            "order": ch.order,
            "title_original": ch.title_original or "",
            "content_original": ch.content_original or "",
        })

    # Run EPUB cleaner logic on copies (identify false chapters, merge bodies)
    deleted_ids: set[int] = set()
    kept: list[dict] = []
    total_lines_removed = 0
    chapters_updated = 0

    for index, ch in enumerate(chapter_copies):
        title = ch["title_original"].strip()
        body = ch["content_original"].strip()
        cleaned_title = CleanerTools.clean_title(title) or title
        cleaned_body, removed_lines = CleanerTools.clean_text_block(body)
        total_lines_removed += removed_lines

        prev = kept[-1] if kept else None
        next_ch = chapter_copies[index + 1] if index + 1 < len(chapter_copies) else None

        if CleanerTools._should_merge_into_previous(cleaned_title, cleaned_body, prev, next_ch):
            if kept and cleaned_body:
                prev_copy = kept[-1]
                prev_body = prev_copy["content_original"].strip()
                merged = CleanerTools._merge_chapter_bodies(prev_body, cleaned_body)
                if merged != prev_copy["content_original"]:
                    prev_copy["content_original"] = merged
                    chapters_updated += 1
            deleted_ids.add(ch["id"])
            continue
        kept.append({**ch, "title_original": cleaned_title, "content_original": cleaned_body})

    # Run TXT cleaner on remaining (kept) chapters
    for ch in kept:
        orig_title = ch["title_original"]
        orig_body = ch["content_original"]
        cleaned_t = CleanerTools.clean_title(orig_title) or orig_title
        cleaned_b, removed = CleanerTools.clean_text_block(orig_body)
        total_lines_removed += removed
        if cleaned_t != orig_title or cleaned_b != orig_body:
            chapters_updated += 1
        ch["title_original"] = cleaned_t
        ch["content_original"] = cleaned_b

    # Re-order
    for new_order, ch in enumerate(kept):
        ch["order"] = new_order

    # Compile preview text
    out = io.StringIO()
    out.write(f"TITLE: {thread.title}\n")
    out.write("-" * 40 + "\n\n")
    for i, ch in enumerate(kept):
        ch_title = ch["title_original"] or f"Chapter {i + 1}"
        out.write(f"=== {ch_title} ===\n\n")
        out.write(ch["content_original"] + "\n\n")
        out.write("-" * 20 + "\n\n")
    cleaned_text = out.getvalue()
    out.close()

    return CleanupPreviewResponse(
        chapters_scanned=len(chapter_copies),
        chapters_deleted=len(deleted_ids),
        chapters_updated=chapters_updated,
        lines_removed=total_lines_removed,
        deleted_chapter_ids=list(deleted_ids),
        cleaned_text=cleaned_text
    )


@router.post("/threads/{thread_id}/cleanup-apply", response_model=CleanerToolResponse)
def apply_cleanup(thread_id: int, db: Session = Depends(get_db)):
    """Apply the cleanup destructively."""
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    epub_summary = CleanerTools.run_epub_cleaner(thread)
    txt_summary = CleanerTools.run_txt_cleaner(thread)
    
    for chapter in list(thread.chapters):
        if chapter.id in epub_summary.deleted_chapter_ids:
            db.delete(chapter)
            
    db.commit()
    
    return CleanerToolResponse(
        thread_id=thread_id,
        tool="full_cleanup",
        chapters_scanned=epub_summary.chapters_scanned,
        chapters_deleted=epub_summary.chapters_deleted,
        chapters_updated=txt_summary.chapters_updated + epub_summary.chapters_updated,
        lines_removed=txt_summary.lines_removed + epub_summary.lines_removed,
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


class StyleGuideUpdate(BaseModel):
    style_guide: Optional[str] = None


@router.put("/threads/{thread_id}/style-guide")
def update_style_guide(thread_id: int, payload: StyleGuideUpdate, db: Session = Depends(get_db)):
    """Update style guide for a thread."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    thread.style_guide = payload.style_guide
    db.commit()
    return {"status": "success", "style_guide": thread.style_guide}


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
        bookmark = UserBookmark(thread_id=thread_id, chapter_id=chapter_id, scroll_progress=0.0)
        db.add(bookmark)
    else:
        # If opening a new/different chapter, reset the scroll progress to 0
        if bookmark.chapter_id != chapter_id:
            bookmark.chapter_id = chapter_id
            bookmark.scroll_progress = 0.0
    db.commit()
    
    current_scroll_progress = bookmark.scroll_progress

    # --- ON-DEMAND READ SCRAPING ---
    if not chapter.content_original and getattr(chapter, "source_url", None):
        import httpx
        from routers.scrape import html_to_markdown
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=15.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TranslatorBot/1.0)"},
            ) as client:
                resp = client.get(chapter.source_url)
                resp.raise_for_status()
            
            fetched_title, fetched_markdown = html_to_markdown(resp.text)
            
            is_vip = False
            if chapter.source_url and "/vip/" in chapter.source_url.lower():
                is_vip = True
            elif fetched_title and "VIP章节" in fetched_title:
                is_vip = True
            elif not fetched_markdown or len(fetched_markdown) < 50:
                is_vip = True

            if is_vip:
                chapter.translation_status = "vip"
                chapter.content_original = "[VIP CHAPTER] Bab ini terkunci atau tidak dapat diakses (VIP)."
            else:
                chapter.content_original = fetched_markdown
                if not chapter.title_original and fetched_title:
                    chapter.title_original = fetched_title
            
            db.commit()
            print(f"[ON-DEMAND READ] Fetched chapter {chapter_id} content from {chapter.source_url}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch on-demand chapter {chapter_id}: {e}")

    # --- PREFETCH TRIGGER (ADR-009) ---
    from services.background_translator import BackgroundTranslator
    from services.ai.settings import resolve_active_base_url, resolve_active_model
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    target_lang = gs.target_language if gs else "Indonesian"
    model = resolve_active_model(gs)
    ai_url = resolve_active_base_url(gs)
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
        source_url=chapter.source_url,
        scroll_progress=current_scroll_progress,
        is_bookmarked=chapter.is_bookmarked,
        fidelity_warning=chapter.fidelity_warning,
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


@router.post("/threads/{thread_id}/fix-truncated")
def fix_truncated_translations(thread_id: int, db: Session = Depends(get_db)):
    """Detect and reset translations that were cut off mid-sentence.
    Uses fidelity_checker.is_truncated_mid_sentence as the single source of truth."""
    from services.fidelity_checker import is_truncated_mid_sentence

    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    reset_count = 0
    for chapter in thread.chapters:
        trans = chapter.content_translated or ''
        orig = chapter.content_original or ''

        if not trans.strip() or len(orig) == 0:
            continue

        if is_truncated_mid_sentence(trans):
            chapter.content_translated = None
            # Preserve translated title - only reset content
            chapter.translation_status = "idle"
            reset_count += 1

    db.commit()
    return {"reset": reset_count}


@router.delete("/threads/{thread_id}/translations")
async def delete_all_translations(thread_id: int, db: Session = Depends(get_db)):
    """Delete all translated content for a thread. Original text is preserved."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    # Cancel any running batch translation first to prevent database conflicts
    from services.background_translator import BackgroundTranslator
    await BackgroundTranslator.stop_batch(thread_id)

    from sqlalchemy import update, delete

    # Bulk delete segments to avoid N+1 queries
    ch_ids_stmt = select(Chapter.id).where(Chapter.thread_id == thread_id)
    db.execute(delete(TranslationSegment).where(TranslationSegment.chapter_id.in_(ch_ids_stmt)))

    # Bulk update chapters to clear translations
    result = db.execute(
        update(Chapter)
        .where(Chapter.thread_id == thread_id)
        .where((Chapter.content_translated != None) | (Chapter.title_translated != None) | (Chapter.translation_status != "idle"))
        .values(
            content_translated=None,
            title_translated=None,
            translation_status="idle"
        )
    )
    affected = result.rowcount
    db.commit()

    return {"chapters_affected": affected}


@router.delete("/threads/{thread_id}/chapters/{chapter_id}")
def delete_chapter(thread_id: int, chapter_id: int, db: Session = Depends(get_db)):
    """Delete a single chapter from a thread."""
    stmt = select(Chapter).where(Chapter.id == chapter_id, Chapter.thread_id == thread_id)
    chapter = db.execute(stmt).scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    deleted_order = chapter.order
    db.delete(chapter)
    db.flush()

    # Re-order remaining chapters
    remaining = db.execute(
        select(Chapter)
        .where(Chapter.thread_id == thread_id)
        .where(Chapter.order > deleted_order)
        .order_by(Chapter.order)
    ).scalars().all()
    for ch in remaining:
        ch.order = ch.order - 1

    db.commit()
    return {"deleted": True, "chapter_id": chapter_id}


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
    from services.fidelity_checker import verify_translation_fidelity
    
    cleaned_translation = ContextEngine.clean_final_translation(body.translated_text, always_hide_thoughts=True)
    chapter.content_translated = cleaned_translation
    
    fidelity = verify_translation_fidelity(
        chapter.content_original or "", cleaned_translation, chapter_id=chapter_id
    )
    if fidelity["is_suspicious"]:
        chapter.fidelity_warning = " | ".join(fidelity["warnings"]) if fidelity.get("warnings") else (
            f"Suspicious translation structure: Original has {fidelity['original_paragraphs']} paragraphs, "
            f"Translated has {fidelity['translated_paragraphs']} paragraphs (ratio: {fidelity['paragraph_ratio']:.2f})."
        )
    else:
        chapter.fidelity_warning = None
        
    db.commit()
    return {"status": "saved"}


from fastapi import Request

@router.put("/threads/{thread_id}/chapters/{chapter_id}/scroll")
@router.post("/threads/{thread_id}/chapters/{chapter_id}/progress")
async def save_chapter_progress_universal(
    thread_id: int, 
    chapter_id: int, 
    request: Request, 
    db: Session = Depends(get_db)
):
    """
    Universal scroll and progress handler supporting application/json, text/plain (sendBeacon),
    and raw JSON bodies while maintaining a single authoritative UserBookmark per thread.
    """
    scroll_progress = 0.0
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            scroll_progress = float(data.get("scroll_progress", 0.0))
        else:
            raw_body = await request.body()
            if raw_body:
                import json
                try:
                    data = json.loads(raw_body.decode("utf-8"))
                    scroll_progress = float(data.get("scroll_progress", 0.0))
                except Exception:
                    scroll_progress = float(raw_body.decode("utf-8").strip() or 0.0)
    except Exception:
        scroll_progress = 0.0

    # Ensure single authoritative UserBookmark per thread
    stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id).order_by(UserBookmark.last_read_at.desc())
    bookmarks = db.execute(stmt).scalars().all()
    
    if not bookmarks:
        bookmark = UserBookmark(thread_id=thread_id, chapter_id=chapter_id, scroll_progress=scroll_progress)
        db.add(bookmark)
    else:
        bookmark = bookmarks[0]
        bookmark.chapter_id = chapter_id
        bookmark.scroll_progress = scroll_progress
        # Clean up any historical duplicate bookmark rows for this thread
        for dup in bookmarks[1:]:
            db.delete(dup)

    db.commit()
    return {"status": "success", "scroll_progress": bookmark.scroll_progress}

class BookmarkedChapterOut(BaseModel):
    id: int
    thread_id: int
    thread_title: str
    order: int
    title_original: Optional[str]
    title_translated: Optional[str]

@router.get("/bookmarks", response_model=List[BookmarkedChapterOut])
def get_all_bookmarks(db: Session = Depends(get_db)):
    """Get all bookmarked chapters."""
    stmt = select(Chapter).where(Chapter.is_bookmarked == True).order_by(Chapter.thread_id, Chapter.order)
    chapters = db.execute(stmt).scalars().all()
    
    results = []
    for ch in chapters:
        thread_title = ch.thread.title if ch.thread.title else ch.thread.original_title
        results.append({
            "id": ch.id,
            "thread_id": ch.thread_id,
            "thread_title": thread_title or "Untitled Thread",
            "order": ch.order,
            "title_original": ch.title_original,
            "title_translated": ch.title_translated
        })
    return results

@router.put("/threads/{thread_id}/chapters/{chapter_id}/bookmark")
def toggle_chapter_bookmark(thread_id: int, chapter_id: int, db: Session = Depends(get_db)):
    """Toggle the bookmark/star status of a chapter."""
    stmt = select(Chapter).where(Chapter.id == chapter_id, Chapter.thread_id == thread_id)
    chapter = db.execute(stmt).scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    
    chapter.is_bookmarked = not chapter.is_bookmarked
    db.commit()
    return {"status": "success", "is_bookmarked": chapter.is_bookmarked}
