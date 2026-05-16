"""
Translation endpoints — connect to LM Studio local API.
POST /api/translate — single-shot translation
POST /api/translate/stream — SSE streaming translation
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
import json

from database import get_db, LorebookEntry, Thread, GlobalSetting

router = APIRouter(prefix="/api", tags=["Translation"])

class TranslateRequest(BaseModel):
    text: str
    thread_id: int | None = None
    model: str | None = None
    target_lang: str = "Indonesian"
    lm_url: str | None = None

class TranslateResponse(BaseModel):
    translation: str
    model_used: str
    lorebook_terms: int

def get_lm_url(req_lm_url: str | None) -> str:
    """Default LM Studio URL. Frontend can override via Settings."""
    return req_lm_url.rstrip("/") if req_lm_url else "http://localhost:1234"

def build_system_prompt(db: Session, thread_id: int | None, target_lang: str) -> str:
    """Build system prompt with contexts and lorebook terms injected."""
    base = (
        f"You are a professional translator. Translate the following text to {target_lang}. "
        "Maintain the original tone, style, and formatting. "
        "Translate naturally — do not translate literally word by word."
    )

    gs = db.query(GlobalSetting).first()
    if gs and gs.global_context:
        base += f"\n\nGlobal Context:\n{gs.global_context}"

    if not thread_id:
        return base

    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread and thread.thread_context:
        base += f"\n\nThread Context:\n{thread.thread_context}"

    entries = db.query(LorebookEntry).filter(LorebookEntry.thread_id == thread_id).all()
    if entries:
        terms = "\n".join(
            f"- {e.original_term} → {e.translated_term}" + (f" ({e.notes})" if e.notes else "")
            for e in entries
        )
        base += f"\n\nIMPORTANT — Use these exact term translations consistently:\n{terms}"

    return base


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest, db: Session = Depends(get_db)):
    """Translate text via LM Studio (non-streaming)."""
    lm_url = get_lm_url(req.lm_url)
    system_prompt = build_system_prompt(db, req.thread_id, req.target_lang)

    lorebook_count = 0
    if req.thread_id:
        lorebook_count = db.query(LorebookEntry).filter(
            LorebookEntry.thread_id == req.thread_id
        ).count()

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.text},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": False,
    }
    if req.model:
        payload["model"] = req.model

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{lm_url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError:
        raise HTTPException(503, f"Cannot connect to LM Studio at {lm_url}. Is it running?")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"LM Studio error: {e}")

    translation = data["choices"][0]["message"]["content"]
    model_used = data.get("model", req.model or "unknown")

    return TranslateResponse(
        translation=translation,
        model_used=model_used,
        lorebook_terms=lorebook_count,
    )


@router.post("/translate/stream")
async def translate_stream(req: TranslateRequest, db: Session = Depends(get_db)):
    """Translate text via LM Studio with SSE streaming."""
    lm_url = get_lm_url(req.lm_url)
    system_prompt = build_system_prompt(db, req.thread_id, req.target_lang)

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.text},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": True,
    }
    if req.model:
        payload["model"] = req.model

    async def generate():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{lm_url}/v1/chat/completions", json=payload
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                obj = json.loads(chunk)
                                delta = obj["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield f"data: {json.dumps({'content': content})}\n\n"
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
        except httpx.ConnectError:
            yield f"data: {json.dumps({'error': 'Cannot connect to LM Studio'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
