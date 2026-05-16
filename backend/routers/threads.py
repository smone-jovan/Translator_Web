"""
Thread & Chapter management endpoints.
GET /api/threads — list all
GET /api/threads/{id} — detail + chapters
DELETE /api/threads/{id} — delete thread + cascade
GET /api/threads/{id}/chapters/{chapter_id} — single chapter content
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Thread, Chapter

router = APIRouter(prefix="/api", tags=["Threads"])


class ChapterOut(BaseModel):
    id: int
    order: int
    title: str | None
    word_count: int
    has_translation: bool

    class Config:
        from_attributes = True


class ThreadOut(BaseModel):
    id: int
    title: str
    source_type: str
    source_url: str | None
    chapter_count: int
    created_at: str | None


class ThreadDetail(ThreadOut):
    chapters: list[ChapterOut]


class ChapterContent(BaseModel):
    id: int
    order: int
    title: str | None
    content_original: str | None
    content_translated: str | None


@router.get("/threads", response_model=list[ThreadOut])
def list_threads(db: Session = Depends(get_db)):
    """List all threads."""
    threads = db.query(Thread).order_by(Thread.id.desc()).all()
    result = []
    for t in threads:
        ch_count = db.query(Chapter).filter(Chapter.thread_id == t.id).count()
        result.append(ThreadOut(
            id=t.id,
            title=t.title,
            source_type=t.source_type,
            source_url=t.source_url,
            chapter_count=ch_count,
            created_at=str(t.created_at) if t.created_at else None,
        ))
    return result


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
def get_thread(thread_id: int, db: Session = Depends(get_db)):
    """Get thread with chapter list."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")

    chapters = db.query(Chapter).filter(
        Chapter.thread_id == thread_id
    ).order_by(Chapter.order).all()

    ch_out = [
        ChapterOut(
            id=c.id,
            order=c.order,
            title=c.title,
            word_count=len((c.content_original or "").split()),
            has_translation=bool(c.content_translated),
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
def get_chapter(thread_id: int, chapter_id: int, db: Session = Depends(get_db)):
    """Get single chapter with full content."""
    chapter = db.query(Chapter).filter(
        Chapter.id == chapter_id,
        Chapter.thread_id == thread_id,
    ).first()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    return ChapterContent(
        id=chapter.id,
        order=chapter.order,
        title=chapter.title,
        content_original=chapter.content_original,
        content_translated=chapter.content_translated,
    )


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, db: Session = Depends(get_db)):
    """Delete thread + all chapters + lorebook (cascade)."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")

    db.delete(thread)
    db.commit()
    return {"deleted": True, "id": thread_id}
