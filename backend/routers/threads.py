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
    title_original: str | None
    title_translated: str | None
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


class TranslationSegmentOut(BaseModel):
    id: int
    order: int
    original_text: str | None
    translated_text: str | None
    display_mode: str

    class Config:
        from_attributes = True


class ChapterContent(BaseModel):
    id: int
    order: int
    title_original: str | None
    title_translated: str | None
    content_original: str | None
    content_translated: str | None
    segments: list[TranslationSegmentOut] = []


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
            title_original=c.title_original,
            title_translated=c.title_translated,
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
        title_original=chapter.title_original,
        title_translated=chapter.title_translated,
        content_original=chapter.content_original,
        content_translated=chapter.content_translated,
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
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
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
    chapter = db.query(Chapter).filter(
        Chapter.id == chapter_id,
        Chapter.thread_id == thread_id,
    ).first()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
        
    chapter.content_translated = body.translated_text
    db.commit()
@router.post("/threads/{thread_id}/translate-titles")
async def translate_titles(thread_id: int, target_lang: str = "Indonesian", db: Session = Depends(get_db)):
    """Bulk translate all chapter titles."""
    from services.ai_provider import AIProvider
    from database import GlobalSetting
    import re

    # Get server-side settings
    gs = db.query(GlobalSetting).first()
    lm_url = gs.lm_url if gs else "http://localhost:1234"

    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    chapters = db.query(Chapter).filter(Chapter.thread_id == thread_id).all()
    if not thread or not chapters:
        return {"count": 0}

    # Filter: Thread title + Chapters
    titles_to_process = []
    indices = [] # -1 for thread title, >=0 for chapter index
    
    # Check if thread title needs translation (simple heuristic: if it has non-ascii)
    if thread.title and any(ord(char) > 127 for char in thread.title):
        titles_to_process.append(thread.title)
        indices.append(-1)

    for i, c in enumerate(chapters):
        if c.title_original and not c.title_translated:
            titles_to_process.append(c.title_original)
            indices.append(i)

    if not titles_to_process:
        return {"count": 0}

    # Build a structured prompt to avoid confusion
    prompt_lines = []
    if -1 in indices:
        prompt_lines.append(f"[BOOK_TITLE]: {thread.title}")
    
    for i, title in enumerate(titles_to_process):
        if indices[i] != -1:
            prompt_lines.append(f"[CHAPTER_{indices[i]}]: {title}")

    sys_prompt = (
        f"You are a professional literary translator. Translate the following book and chapter titles into {target_lang}.\n"
        "Instructions:\n"
        "1. Maintain the EXACT same labels ([BOOK_TITLE] or [CHAPTER_X]).\n"
        "2. Translate only the text AFTER the colon.\n"
        "3. Hanzi/Pinyin should be translated into evocative and meaningful titles.\n"
        "4. Return one title per line."
    )
    user_prompt = "\n".join(prompt_lines)

    try:
        response = await AIProvider.generate_batch(sys_prompt, user_prompt, base_url=lm_url)
        translated_lines = [line.strip() for line in response.split("\n") if line.strip()]
        
        count = 0
        for line in translated_lines:
            if ":" not in line: continue
            label, translated_title = line.split(":", 1)
            translated_title = translated_title.strip()

            if "[BOOK_TITLE]" in label:
                thread.title = translated_title
                count += 1
            elif "[CHAPTER_" in label:
                try:
                    ch_idx = int(label.replace("[CHAPTER_", "").replace("]", ""))
                    chapters[ch_idx].title_translated = translated_title
                    count += 1
                except: continue
        
        db.commit()
        return {"count": count}
    except Exception as e:
        raise HTTPException(500, f"AI Error: {str(e)}")
