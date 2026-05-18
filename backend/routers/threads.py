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

from database import get_db, Thread, Chapter, GlobalSetting, UserBookmark

router = APIRouter(prefix="/api", tags=["Threads"])


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
    scroll_progress: float = 0.0
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
