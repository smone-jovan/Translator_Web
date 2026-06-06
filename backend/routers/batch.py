from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Optional

from database import get_db, Thread, GlobalSetting, LorebookEntry
from services.background_translator import BackgroundTranslator, active_batches
from services.ai.settings import resolve_active_base_url, resolve_active_model

router = APIRouter(prefix="/api", tags=["Batch Translation"])

class BatchTranslateRequest(BaseModel):
    chapter_ids: List[int]
    ai_extract: bool = True
    target_lang: Optional[str] = "Indonesian"
    overwrite: bool = True
    translation_mode: str = "quality"  # "quality" or "fast"
    fetch_only: bool = False

@router.post("/threads/{thread_id}/batch-translate")
async def batch_translate(
    thread_id: int, 
    req: BatchTranslateRequest,
    db: Session = Depends(get_db)
):
    """Trigger sequential, GPU-friendly batch translation for multiple chapters."""
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
    lm_url = resolve_active_base_url(gs)
    model = resolve_active_model(gs)
    target_lang = req.target_lang or (gs.target_language if gs else "Indonesian")
    translation_mode = req.translation_mode or (gs.translation_mode if gs else "quality")

    # 3. Start sequential queue
    await BackgroundTranslator.start_batch(
        thread_id=thread_id,
        chapter_ids=req.chapter_ids,
        target_lang=target_lang,
        model=model,
        lm_url=lm_url,
        force_extract=req.ai_extract,
        force_overwrite=req.overwrite,
        translation_mode=translation_mode,
        fetch_only=req.fetch_only
    )

    return {
        "status": "started",
        "batch_size": len(req.chapter_ids),
        "lore_count": lore_count,
        "recommend_extract": lore_count < 40
    }


@router.get("/threads/{thread_id}/batch-status")
def get_batch_status(thread_id: int, db: Session = Depends(get_db)):
    """Get the active stateful batch translation progress for a specific thread."""
    batch = active_batches.get(thread_id)
    
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    from services.ai.secrets import get_key_stats
    stats = get_key_stats(gs.llm_provider if gs else "lm_studio", gs)
    
    if not batch:
        return {
            "active": False,
            "total": 0,
            "completed": 0,
            "current_chapter_id": None,
            "current_chapter_title": "",
            "failed_ids": [],
            "quota_exhausted": False,
            "total_keys": stats["total"],
            "exhausted_keys": stats["exhausted"]
        }
    return {
        "active": True,
        "total": batch.total,
        "completed": batch.completed,
        "current_chapter_id": batch.current_chapter_id,
        "current_chapter_title": batch.current_chapter_title,
        "failed_ids": batch.failed_ids,
        "quota_exhausted": getattr(batch, "quota_exhausted", False),
        "total_keys": stats["total"],
        "exhausted_keys": stats["exhausted"]
    }


@router.post("/threads/{thread_id}/batch-stop")
async def stop_batch_translation(thread_id: int):
    """Gracefully cancel and stop active batch translation queue."""
    await BackgroundTranslator.stop_batch(thread_id)
    return {"status": "stopped"}
