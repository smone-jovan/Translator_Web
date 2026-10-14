from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Optional

from database import get_db, Thread, GlobalSetting, LorebookEntry, get_db_workspace, make_workspace_key, normalize_workspace
from services.background_translator import BackgroundTranslator, active_batches, recent_finished_batches
from services.ai.settings import resolve_active_base_url, resolve_active_model

router = APIRouter(prefix="/api", tags=["Batch Translation"])

class BatchTranslateRequest(BaseModel):
    chapter_ids: List[int]
    ai_extract: bool = True
    target_lang: Optional[str] = "Indonesian"
    overwrite: bool = True
    translation_mode: str = "quality"  # "quality" or "fast"
    fetch_only: bool = False
    load_mode: Optional[str] = None  # "soft" or "hard"

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
    load_mode = req.load_mode or (gs.prefetch_mode if gs else "soft")
    if req.load_mode in ("soft", "hard") and gs:
        gs.prefetch_mode = req.load_mode
        db.commit()

    ws = get_db_workspace(db)

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
        fetch_only=req.fetch_only,
        load_mode=load_mode,
        workspace=ws,
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
    ws = normalize_workspace(get_db_workspace(db))
    batch = active_batches.get(make_workspace_key(ws, thread_id))
    if batch and getattr(batch, "workspace", "main").lower() != ws:
        batch = None

    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    from services.ai.secrets import get_key_stats
    stats = get_key_stats(gs.llm_provider if gs else "lm_studio", gs)

    # Check if batch exists but has already finished or stopped
    if batch and (getattr(batch, "is_stopped", False) is True or getattr(batch, "is_completed", False) is True):
        b_status = getattr(batch, "status", "completed")
        if not isinstance(b_status, str):
            b_status = "completed"
        raw_failed = getattr(batch, "failed_ids", [])
        failed_list = list(raw_failed) if isinstance(raw_failed, (list, tuple)) else []
        return {
            "active": False,
            "status": b_status,
            "is_waiting": False,
            "total": batch.total,
            "completed": batch.completed,
            "current_chapter_id": None,
            "current_chapter_title": "",
            "failed_ids": failed_list,
            "quota_exhausted": bool(getattr(batch, "quota_exhausted", False)),
            "total_keys": stats["total"],
            "exhausted_keys": stats["exhausted"],
        }

    if not batch:
        # Check recent_finished_batches for this thread
        last_b = recent_finished_batches.get(ws)
        if last_b and last_b.get("thread_id") == thread_id:
            return {
                "active": False,
                "status": last_b.get("status", "completed"),
                "is_waiting": False,
                "total": last_b.get("total", 0),
                "completed": last_b.get("completed", 0),
                "current_chapter_id": None,
                "current_chapter_title": "",
                "failed_ids": last_b.get("failed_ids", []),
                "quota_exhausted": last_b.get("quota_exhausted", False),
                "total_keys": stats["total"],
                "exhausted_keys": stats["exhausted"],
            }

        return {
            "active": False,
            "status": "idle",
            "is_waiting": False,
            "total": 0,
            "completed": 0,
            "current_chapter_id": None,
            "current_chapter_title": "",
            "failed_ids": [],
            "quota_exhausted": False,
            "total_keys": stats["total"],
            "exhausted_keys": stats["exhausted"]
        }
    b_status = getattr(batch, "status", "running")
    if not isinstance(b_status, str):
        b_status = "running"
    raw_failed = getattr(batch, "failed_ids", [])
    failed_list = list(raw_failed) if isinstance(raw_failed, (list, tuple)) else []
    return {
        "active": True,
        "status": b_status,
        "is_waiting": bool(getattr(batch, "is_waiting", False)),
        "total": batch.total,
        "completed": batch.completed,
        "current_chapter_id": batch.current_chapter_id,
        "current_chapter_title": batch.current_chapter_title,
        "failed_ids": failed_list,
        "quota_exhausted": bool(getattr(batch, "quota_exhausted", False)),
        "total_keys": stats["total"],
        "exhausted_keys": stats["exhausted"]
    }


@router.post("/threads/{thread_id}/batch-stop")
async def stop_batch_translation(thread_id: int, db: Session = Depends(get_db)):
    """Gracefully cancel and stop active batch translation queue."""
    ws = get_db_workspace(db)
    await BackgroundTranslator.stop_batch(thread_id, workspace=ws)
    return {"status": "stopped"}
