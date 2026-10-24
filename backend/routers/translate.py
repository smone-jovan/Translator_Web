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
from database import get_db, LorebookEntry, Chapter, Thread, SessionLocal, GlobalSetting, get_db_workspace, make_workspace_key
from services.context_engine import ContextEngine
from services.ai.factory import AIProviderFactory
from services.ai.chunking import maybe_chunk
from services.ai.index_translate import (
    build_index_translate_messages,
    collect_glossary_pairs,
    is_index_translate_model,
)
from services.ai.settings import resolve_active_base_url, resolve_active_model, get_chapter_translation_max_tokens
from services.task_registry import spawn_background_task

SSE_HEARTBEAT_SECONDS = 15

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
    thread_id: int | None = None
    chapter_id: int | None = None

from services.background_translator import BackgroundTranslator, translation_queues, active_tasks

async def get_lm_url(req_lm_url: str | None, db: Session) -> str:
    # URL dari klien selalu lewat resolver: untuk provider cloud hanya host tepercaya
    # yang diterima, agar API key tidak terkirim ke URL pilihan klien (ADR-126).
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    return resolve_active_base_url(gs, req_lm_url)

@router.post("/translate/stream")
async def translate_stream(req: TranslateRequest, db: Session = Depends(get_db)):
    """SSE streaming that triggers background persistence."""
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    
    ai_url = await get_lm_url(req.lm_url, db)
    target_lang = req.target_lang if req.target_lang != "Indonesian" else (gs.target_language if gs else "Indonesian")
    selected_model = resolve_active_model(gs, req.model)

    if not req.chapter_id:
        raise HTTPException(400, "chapter_id is required for streaming")

    ws = get_db_workspace(db)

    # Register the listener BEFORE the job exists, so a job that finishes instantly
    # (error / skip / chapter missing) still delivers [DONE] to this client.
    q = asyncio.Queue()
    queue_key = make_workspace_key(ws, req.chapter_id)
    translation_queues.setdefault(queue_key, []).append(q)

    # Start the persistent background job if needed
    spawn_background_task(
        BackgroundTranslator.run_chapter_translation(
            chapter_id=req.chapter_id,
            thread_id=req.thread_id,
            target_lang=target_lang,
            model=selected_model,
            lm_url=ai_url,
            force_overwrite=req.force_overwrite,
            workspace=ws,
        )
    )

    async def sse_wrapper():
        try:
            while True:
                try:
                    content = await asyncio.wait_for(q.get(), timeout=SSE_HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    if queue_key not in active_tasks and q.empty():
                        break  # no job is producing for this chapter any more
                    yield ": keep-alive\n\n"
                    continue
                if content == "[DONE]":
                    break
                if isinstance(content, dict) and "final_text" in content:
                    yield f"data: {json.dumps(content)}\n\n"
                elif isinstance(content, str) and content.startswith("FINAL_TEXT:"):
                    clean_text = content[len("FINAL_TEXT:"):]
                    yield f"data: {json.dumps({'final_text': clean_text})}\n\n"
                else:
                    yield f"data: {json.dumps({'content': content})}\n\n"
        finally:
            if queue_key in translation_queues and q in translation_queues[queue_key]:
                translation_queues[queue_key].remove(q)
                if not translation_queues[queue_key]:
                    del translation_queues[queue_key]

        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")

@router.post("/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest, db: Session = Depends(get_db)):
    """Translate text via active AI provider (non-streaming) and persist to Thread/Chapter."""
    if not req.text or not req.text.strip():
        raise HTTPException(400, "Text is required")

    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()

    ai_url = await get_lm_url(req.lm_url, db)
    target_lang = req.target_lang if req.target_lang != "Indonesian" else (gs.target_language if gs else "Indonesian")
    selected_model = resolve_active_model(gs, req.model)
    translation_mode = gs.translation_mode if gs else "quality"

    provider = AIProviderFactory.get_provider(base_url=ai_url, model=selected_model, db_session=db)
    system_prompt = ContextEngine.build_translation_prompt(
        db, req.thread_id, target_lang, req.text, model=selected_model, translation_mode=translation_mode
    )
    max_tokens = get_chapter_translation_max_tokens(gs)

    import re
    image_pattern = re.compile(r"(!\[.*?\]\(.*?\))")
    protected_images = image_pattern.findall(req.text)
    protected_text = req.text
    # Normalize repeating symbol bursts before feeding into LLM
    protected_text = re.sub(r"([□■•�■-◿])\1{3,}", r"\1\1\1", protected_text)
    for i, img_md in enumerate(protected_images):
        protected_text = protected_text.replace(img_md, f"\n❖IMAGE_{i}❖\n")

    if is_index_translate_model(selected_model):
        # Index-Translate expects its own single-message template, not the long system prompt.
        glossary = collect_glossary_pairs(db, req.thread_id, req.text)

        def build_request(text: str) -> list:
            return build_index_translate_messages(text, target_lang, glossary)

        messages = build_request(protected_text)
        provider = maybe_chunk(provider, source_text=protected_text, message_builder=build_request)
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": protected_text},
        ]
        provider = maybe_chunk(provider)

    try:
        translation = await provider.chat_completion(messages=messages, temperature=getattr(provider, "translation_temperature", 0.3), max_tokens=max_tokens)
        model_used = selected_model or "unknown"

        always_hide_thoughts = getattr(gs, "always_hide_thoughts", 1) if gs else 1
        clean_translation = ContextEngine.clean_final_translation(
            translation,
            always_hide_thoughts=bool(always_hide_thoughts)
        )

        for i, img_md in enumerate(protected_images):
            clean_translation = re.sub(rf"❖(?:IMAGE|GAMBAR|Image|gambar)_{i}❖", img_md, clean_translation, flags=re.IGNORECASE)
            if img_md not in clean_translation:
                clean_translation += f"\n\n{img_md}\n\n"

        # Derive a clean title from the first non-empty line of the input text
        first_line = next(
            (line.strip().lstrip("#").strip() for line in req.text.splitlines() if line.strip()),
            "Untitled Text",
        )[:120] or "Untitled Text"

        resolved_thread_id = req.thread_id
        resolved_chapter_id = req.chapter_id

        from services.fidelity_checker import verify_translation_fidelity

        if req.chapter_id:
            chapter = db.execute(select(Chapter).where(Chapter.id == req.chapter_id)).scalar_one_or_none()
            if chapter:
                resolved_thread_id = chapter.thread_id
                ContextEngine.auto_save_glossary(db, resolved_thread_id, translation)
                clean_translation = ContextEngine.enforce_glossary_locking(db, resolved_thread_id, clean_translation)
                chapter.content_translated = clean_translation
                chapter.translation_status = "done"
                fidelity = verify_translation_fidelity(chapter.content_original or "", clean_translation, chapter_id=chapter.id)
                chapter.fidelity_warning = " | ".join(fidelity["warnings"]) if fidelity.get("is_suspicious") and fidelity.get("warnings") else None
                db.commit()
        elif req.thread_id:
            thread = db.execute(select(Thread).where(Thread.id == req.thread_id)).scalar_one_or_none()
            if not thread:
                raise HTTPException(404, "Thread not found")
            ContextEngine.auto_save_glossary(db, thread.id, translation)
            clean_translation = ContextEngine.enforce_glossary_locking(db, thread.id, clean_translation)
            max_order_val = db.execute(
                select(func.max(Chapter.order)).where(Chapter.thread_id == thread.id)
            ).scalar()
            next_order = 0 if max_order_val is None else max_order_val + 1
            chapter = Chapter(
                thread_id=thread.id,
                order=next_order,
                title_original=first_line,
                content_original=req.text,
                content_translated=clean_translation,
                translation_status="done",
            )
            db.add(chapter)
            db.flush()
            fidelity = verify_translation_fidelity(req.text, clean_translation, chapter_id=chapter.id)
            chapter.fidelity_warning = " | ".join(fidelity["warnings"]) if fidelity.get("is_suspicious") and fidelity.get("warnings") else None
            db.commit()
            db.refresh(chapter)
            resolved_chapter_id = chapter.id
        else:
            thread = Thread(
                title=first_line,
                original_title=first_line,
                source_type="text",
            )
            db.add(thread)
            db.flush()
            resolved_thread_id = thread.id
            ContextEngine.auto_save_glossary(db, thread.id, translation)
            clean_translation = ContextEngine.enforce_glossary_locking(db, thread.id, clean_translation)
            chapter = Chapter(
                thread_id=thread.id,
                order=0,
                title_original=first_line,
                content_original=req.text,
                content_translated=clean_translation,
                translation_status="done",
            )
            db.add(chapter)
            db.flush()
            fidelity = verify_translation_fidelity(req.text, clean_translation, chapter_id=chapter.id)
            chapter.fidelity_warning = " | ".join(fidelity["warnings"]) if fidelity.get("is_suspicious") and fidelity.get("warnings") else None
            db.commit()
            db.refresh(chapter)
            resolved_chapter_id = chapter.id

        lorebook_count = 0
        if resolved_thread_id:
            count_stmt = select(func.count(LorebookEntry.id)).where(LorebookEntry.thread_id == resolved_thread_id)
            lorebook_count = db.execute(count_stmt).scalar() or 0

        return TranslateResponse(
            translation=clean_translation,
            model_used=model_used,
            lorebook_terms=lorebook_count,
            thread_id=resolved_thread_id,
            chapter_id=resolved_chapter_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log full error server-side for debugging, but don't leak internals to client
        print(f"[ERROR] Translation failed: {e}")
        safe_msg = "Translation request failed. Check server logs for details."
        error_str = str(e).lower()
        if "connection" in error_str or "timeout" in error_str:
            safe_msg = "AI provider connection failed. Is the LLM server running?"
        elif "api_key" in error_str or "auth" in error_str or "401" in error_str:
            safe_msg = "AI provider authentication failed. Check your API key."
        elif "rate" in error_str or "429" in error_str or "quota" in error_str:
            safe_msg = "AI provider rate limit reached. Please wait and try again."
        raise HTTPException(502, safe_msg)
