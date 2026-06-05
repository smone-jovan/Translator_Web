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
    style_guide: Optional[str] = None
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
    scroll_progress: float = 0.0
    is_bookmarked: bool = False
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
        scroll_progress=current_scroll_progress,
        is_bookmarked=chapter.is_bookmarked,
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
    """Detect and reset translations that were cut off mid-sentence."""
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

        last = trans.rstrip()[-1:] if trans.strip() else ''
        ends_properly = last in '.!??"」』~*-)\u2026'

        if not ends_properly:
            chapter.content_translated = None
            # Preserve translated title - only reset content
            chapter.translation_status = "idle"
            reset_count += 1

    db.commit()
    return {"reset": reset_count}


@router.delete("/threads/{thread_id}/translations")
def delete_all_translations(thread_id: int, db: Session = Depends(get_db)):
    """Delete all translated content for a thread. Original text is preserved."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    affected = 0
    for chapter in thread.chapters:
        has_translation = chapter.content_translated or chapter.title_translated or chapter.translation_status == "done"
        if has_translation:
            chapter.content_translated = None
            chapter.title_translated = None
            chapter.translation_status = "idle"
            affected += 1
        for seg in list(chapter.segments):
            db.delete(seg)

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
    chapter.content_translated = ContextEngine.clean_final_translation(body.translated_text, always_hide_thoughts=True)
    db.commit()
    return {"status": "saved"}


class ScrollUpdatePayload(BaseModel):
    scroll_progress: float


@router.put("/threads/{thread_id}/chapters/{chapter_id}/scroll")
def update_chapter_scroll(thread_id: int, chapter_id: int, payload: ScrollUpdatePayload, db: Session = Depends(get_db)):
    """Update scroll progress for a thread's active reading session."""
    stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id, UserBookmark.chapter_id == chapter_id)
    bookmark = db.execute(stmt).scalar_one_or_none()
    if not bookmark:
        bookmark = UserBookmark(thread_id=thread_id, chapter_id=chapter_id, scroll_progress=payload.scroll_progress)
        db.add(bookmark)
    else:
        bookmark.scroll_progress = payload.scroll_progress
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
        thread_title = ch.thread.title_translated if ch.thread.title_translated else ch.thread.title_original
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
