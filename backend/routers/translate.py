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

class TranslateResponse(BaseModel):
    translation: str
    model_used: str
    lorebook_terms: int

def get_lm_url(req_lm_url: str | None) -> str:
    if req_lm_url:
        return req_lm_url.rstrip("/")
    return "http://localhost:1234"

# In-memory progress tracker (optional but helps for realtime SSE)
translation_queues = {}

async def run_persistent_translation(req: TranslateRequest, payload: dict):
    """Background task to run translation and save to DB incrementally."""
    chapter_id = req.chapter_id
    if not chapter_id: return

    # Set status to processing
    with SessionLocal() as db:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if chapter:
            chapter.translation_status = "processing"
            chapter.content_translated = "" # Start fresh or keep? For now start fresh
            db.commit()

    ai = AIProvider(get_lm_url(req.lm_url))
    full_content = ""
    chunk_count = 0
    
    try:
        async for content in ai.stream_chat(payload):
            full_content += content
            chunk_count += 1
            
            # Put into queue for active SSE listeners
            if chapter_id in translation_queues:
                for q in translation_queues[chapter_id]:
                    await q.put(content)
            
            # Periodically save to DB
            if chunk_count % 15 == 0:
                with SessionLocal() as db:
                    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
                    if chapter:
                        chapter.content_translated = full_content
                        db.commit()

        # Finalize
        with SessionLocal() as db:
            if req.thread_id:
                ContextEngine.auto_save_glossary(db, req.thread_id, full_content)
            
            chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
            if chapter:
                chapter.content_translated = full_content
                chapter.translation_status = "done"
                db.commit()
                print(f"✅ Background translation DONE for chapter {chapter_id}")

    except Exception as e:
        print(f"❌ Background translation ERROR: {e}")
        with SessionLocal() as db:
            chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
            if chapter:
                chapter.translation_status = "error"
                db.commit()
    finally:
        # Clean up queue when done
        if chapter_id in translation_queues:
            for q in translation_queues[chapter_id]:
                await q.put("[DONE]")

@router.post("/translate/stream")
async def translate_stream(req: TranslateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """SSE streaming that triggers background persistence."""
    gs = db.query(GlobalSetting).first()
    
    ai_url = get_lm_url(req.lm_url or (gs.lm_url if gs else None))
    target_lang = req.target_lang if req.target_lang != "Indonesian" else (gs.target_language if gs else "Indonesian")
    selected_model = req.model or (gs.lm_model if gs else None)

    system_prompt = ContextEngine.build_translation_prompt(db, req.thread_id, target_lang)

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.text},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
        "stream": True,
    }
    if selected_model:
        payload["model"] = selected_model
    
    # Update AI Provider with correct URL
    # (Note: AI Provider is instantiated inside background task, passing it there)
    req.lm_url = ai_url
    req.model = selected_model
    req.target_lang = target_lang

    # Check if already processing
    if req.chapter_id:
        chapter = db.query(Chapter).filter(Chapter.id == req.chapter_id).first()
        if chapter and chapter.translation_status == "processing":
            # Just subscribe to the existing stream?
            # For simplicity, we just start a new one if it's not truly managed, 
            # but ideally we'd check translation_queues.
            pass

    # IMPORTANT: Do not use FastAPI's `BackgroundTasks` here!
    # BackgroundTasks run *after* the response is fully sent. Because this is a 
    # StreamingResponse that blocks waiting for the task's output, using BackgroundTasks 
    # will cause a deadlock (the stream waits for the task, the task waits for the stream to close).
    # See documentation-and-adrs: Document Known Gotchas.
    # Start the persistent background job ONLY if not already running
    if req.chapter_id not in translation_queues:
        asyncio.create_task(run_persistent_translation(req, payload))

    async def sse_wrapper():
        # This wrapper can also just wait for the queue
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
    gs = db.query(GlobalSetting).first()
    
    ai_url = get_lm_url(req.lm_url or (gs.lm_url if gs else None))
    target_lang = req.target_lang if req.target_lang != "Indonesian" else (gs.target_language if gs else "Indonesian")
    selected_model = req.model or (gs.lm_model if gs else None)

    ai = AIProvider(ai_url)
    system_prompt = ContextEngine.build_translation_prompt(db, req.thread_id, target_lang)

    lorebook_count = 0
    if req.thread_id:
        lorebook_count = db.query(LorebookEntry).filter(LorebookEntry.thread_id == req.thread_id).count()

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

        return TranslateResponse(
            translation=translation,
            model_used=model_used,
            lorebook_terms=lorebook_count,
        )
    except Exception as e:
        raise HTTPException(502, str(e))
