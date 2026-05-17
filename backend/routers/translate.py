"""
Translation endpoints — connect to LM Studio local API.
POST /api/translate — single-shot translation
POST /api/translate/stream — SSE streaming translation
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json
import asyncio

from sqlalchemy import select, func
from database import get_db, LorebookEntry, Chapter, SessionLocal, GlobalSetting
from services.context_engine import ContextEngine
from services.ai_provider import AIProvider

router = APIRouter(prefix="/api", tags=["Translation"])

class TranslateRequest(BaseModel):
    text: str
    thread_id: int | None = None
    chapter_id: int | None = None
    model: str | None = None
    target_lang: str = "Indonesian"
    lm_url: str | None = None
    force_overwrite: bool = False

class TranslateResponse(BaseModel):
    translation: str
    model_used: str
    lorebook_terms: int

from services.background_translator import BackgroundTranslator, translation_queues

async def get_lm_url(req_lm_url: str | None, db: Session) -> str:
    if req_lm_url:
        return req_lm_url.rstrip("/")
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    return (gs.lm_url if gs else "http://localhost:1234").rstrip("/")

@router.post("/translate/stream")
async def translate_stream(req: TranslateRequest, db: Session = Depends(get_db)):
    """SSE streaming that triggers background persistence."""
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    
    ai_url = await get_lm_url(req.lm_url, db)
    target_lang = req.target_lang if req.target_lang != "Indonesian" else (gs.target_language if gs else "Indonesian")
    selected_model = req.model or (gs.lm_model if gs else None)

    if not req.chapter_id:
        raise HTTPException(400, "chapter_id is required for streaming")

    # Start the persistent background job if needed
    asyncio.create_task(
        BackgroundTranslator.run_chapter_translation(
            chapter_id=req.chapter_id,
            thread_id=req.thread_id,
            target_lang=target_lang,
            model=selected_model,
            lm_url=ai_url,
            force_overwrite=req.force_overwrite
        )
    )

    async def sse_wrapper():
        q = asyncio.Queue()
        if req.chapter_id not in translation_queues:
            translation_queues[req.chapter_id] = []
        translation_queues[req.chapter_id].append(q)
        
        try:
            while True:
                content = await q.get()
                if content == "[DONE]":
                    break
                yield f"data: {json.dumps({'content': content})}\n\n"
        finally:
            translation_queues[req.chapter_id].remove(q)
            if not translation_queues[req.chapter_id]:
                del translation_queues[req.chapter_id]
        
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")

@router.post("/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest, db: Session = Depends(get_db)):
    """Translate text via LM Studio (non-streaming)."""
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    
    ai_url = await get_lm_url(req.lm_url or (gs.lm_url if gs else None), db)
    target_lang = req.target_lang if req.target_lang != "Indonesian" else (gs.target_language if gs else "Indonesian")
    selected_model = req.model or (gs.lm_model if gs else None)

    ai = AIProvider(ai_url)
    system_prompt = ContextEngine.build_translation_prompt(db, req.thread_id, target_lang)

    lorebook_count = 0
    if req.thread_id:
        count_stmt = select(func.count(LorebookEntry.id)).where(LorebookEntry.thread_id == req.thread_id)
        lorebook_count = db.execute(count_stmt).scalar() or 0

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.text},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": False,
    }
    if selected_model:
        payload["model"] = selected_model

    try:
        data = await ai.chat_completion(payload)
        translation = data["choices"][0]["message"]["content"]
        model_used = data.get("model", selected_model or "unknown")

        if req.thread_id:
            ContextEngine.auto_save_glossary(db, req.thread_id, translation)

        clean_translation = ContextEngine.strip_translator_notes(translation)

        return TranslateResponse(
            translation=clean_translation,
            model_used=model_used,
            lorebook_terms=lorebook_count,
        )
    except Exception as e:
        raise HTTPException(502, str(e))
