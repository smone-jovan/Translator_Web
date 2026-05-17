from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json
import re

from sqlalchemy import select
from database import get_db, GlobalSetting, Thread, Chapter
from services.ai_provider import AIProvider

router = APIRouter(prefix="/api", tags=["Context"])

class ContextUpdate(BaseModel):
    context: str

class GlobalSettingsUpdate(BaseModel):
    lm_url: str | None = None
    lm_model: str | None = None
    target_language: str | None = None
    prefetch_enabled: int | None = None
    prefetch_count: int | None = None
    prefetch_mode: str | None = None

class ExtractRequest(BaseModel):
    lm_url: str | None = None
    model: str | None = None
    chapter_count: int = 25
    sample_size: int = 1000

class ExtractedTerm(BaseModel):
    original_term: str
    translated_term: str | None = None
    notes: str | None = None

@router.get("/global-context")
def get_global_context(db: Session = Depends(get_db)):
    stmt = select(GlobalSetting)
    gs = db.execute(stmt).scalar_one_or_none()
    return {
        "global_context": gs.global_context if gs else "",
        "lm_url": gs.lm_url if gs else "http://localhost:1234",
        "lm_model": gs.lm_model if gs else None,
        "target_language": gs.target_language if gs else "Indonesian",
        "prefetch_enabled": gs.prefetch_enabled if gs else 0,
        "prefetch_count": gs.prefetch_count if gs else 2,
        "prefetch_mode": gs.prefetch_mode if gs else "soft"
    }

@router.post("/global-context")
def update_global_context(req: ContextUpdate, db: Session = Depends(get_db)):
    stmt = select(GlobalSetting)
    gs = db.execute(stmt).scalar_one_or_none()
    if not gs:
        gs = GlobalSetting()
        db.add(gs)
    gs.global_context = req.context
    db.commit()
    return {"status": "ok"}

@router.post("/settings")
def update_settings(req: GlobalSettingsUpdate, db: Session = Depends(get_db)):
    stmt = select(GlobalSetting)
    gs = db.execute(stmt).scalar_one_or_none()
    if not gs:
        gs = GlobalSetting()
        db.add(gs)
    
    if req.lm_url is not None: gs.lm_url = req.lm_url
    if req.lm_model is not None: gs.lm_model = req.lm_model
    if req.target_language is not None: gs.target_language = req.target_language
    if req.prefetch_enabled is not None: gs.prefetch_enabled = req.prefetch_enabled
    if req.prefetch_count is not None: gs.prefetch_count = req.prefetch_count
    if req.prefetch_mode is not None: gs.prefetch_mode = req.prefetch_mode
    
    db.commit()
    return {"status": "ok"}

@router.post("/threads/{thread_id}/extract-context")
async def extract_thread_context(thread_id: int, req: ExtractRequest, db: Session = Depends(get_db)):
    """Analyze chapter text to extract key terms (names, locations, etc)."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    # 1. Identify starting point (last_read or first chapter)
    from database import UserBookmark
    bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id)
    bookmark = db.execute(bookmark_stmt).scalar_one_or_none()
    
    start_order = 0
    if bookmark:
        last_ch_stmt = select(Chapter).where(Chapter.id == bookmark.chapter_id)
        last_ch = db.execute(last_ch_stmt).scalar_one_or_none()
        if last_ch:
            start_order = last_ch.order

    # 2. Fetch up to X chapters starting from start_order
    ch_stmt = (
        select(Chapter)
        .where(Chapter.thread_id == thread_id, Chapter.order >= start_order)
        .order_by(Chapter.order)
        .limit(req.chapter_count)
    )
    chapters = db.execute(ch_stmt).scalars().all()
    
    if not chapters:
        return {"terms": []}

    # 3. Combine text samples from all fetched chapters
    text_parts = []
    total_chars = 0
    for ch in chapters:
        if ch.content_original:
            sample = ch.content_original[:req.sample_size]
            text_parts.append(f"--- Chapter {ch.order + 1}: {ch.title_original} ---\n{sample}")
            total_chars += len(sample)
    
    full_text = "\n\n".join(text_parts)
    if not full_text:
        return {"terms": []}

    # 4. Get Global Settings for Prompt
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    global_rules = gs.global_context if gs else ""
    target_lang = gs.target_language if gs else "Indonesian"

    # Estimated tokens (Chinese characters average ~0.8 tokens per character in Llama-3/Mistral tokenizers)
    # plus static instructions prompt (~150 tokens) and global rules (~0.25 tokens per char)
    est_tokens = int(150 + (len(global_rules) / 4) + (total_chars * 0.8))
    
    prompt = (
        f"You are an expert literary analyst specializing in Chinese web novels.\n"
        f"Your task is to identify and extract key proper nouns from the text provided, following these rules:\n\n"
        f"RULES & ETHICS (MANDATORY):\n{global_rules}\n\n"
        f"EXTRACTION GUIDELINES:\n"
        f"1. Focus on the MOST FREQUENT and SIGNIFICANT terms (Protagonist, key items, recurring locations).\n"
        f"2. Ignore generic or common words. Only take high-priority patterns.\n"
        f"3. Provide: The original Chinese term, a natural {target_lang} translation, and brief notes.\n"
        f"4. Format as a JSON list: [{{ \"original_term\": \"...\", \"translated_term\": \"...\", \"notes\": \"...\" }}].\n"
    )
    
    ai_url = req.lm_url or (gs.lm_url if gs else "http://localhost:1234")
    ai = AIProvider(ai_url)
    
    payload = {
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": full_text},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
        "stream": False
    }
    if req.model:
        payload["model"] = req.model
    
    try:
        data = await ai.chat_completion(payload)
        content = data["choices"][0]["message"]["content"]
        
        # Robust parsing logic
        # 1. Try to find JSON block
        json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
        if json_match:
            try:
                terms = json.loads(json_match.group(0))
                return {
                    "terms": terms, 
                    "metadata": {
                        "est_input_tokens": est_tokens,
                        "total_chars": total_chars
                    }
                }
            except:
                pass

        # 2. Fallback to manual line parsing (Simplified for new format)
        manual_terms = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip().lstrip("-*•").strip()
            if ":" in line:
                parts = line.split(":", 1)
                term = parts[0].strip()
                if len(term) < 50 and term:
                    manual_terms.append({
                        "original_term": term,
                        "translated_term": "", # Placeholder if manual fallback fails
                        "notes": parts[1].strip()
                    })
        
        return {"terms": manual_terms}

    except Exception as e:
        raise HTTPException(502, str(e))
