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

class ExtractRequest(BaseModel):
    lm_url: str | None = None
    model: str | None = None

class ExtractedTerm(BaseModel):
    original_term: str
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
        "prefetch_enabled": gs.prefetch_enabled if gs else 0
    }

@router.post("/global-context")
def update_global_context(body: ContextUpdate, db: Session = Depends(get_db)):
    stmt = select(GlobalSetting)
    gs = db.execute(stmt).scalar_one_or_none()
    if not gs:
        gs = GlobalSetting(global_context=body.context)
        db.add(gs)
    else:
        gs.global_context = body.context
    db.commit()
    return {"global_context": gs.global_context}

@router.post("/settings")
def update_settings(body: GlobalSettingsUpdate, db: Session = Depends(get_db)):
    stmt = select(GlobalSetting)
    gs = db.execute(stmt).scalar_one_or_none()
    if not gs:
        gs = GlobalSetting()
        db.add(gs)
    
    if body.lm_url is not None: gs.lm_url = body.lm_url
    if body.lm_model is not None: gs.lm_model = body.lm_model
    if body.target_language is not None: gs.target_language = body.target_language
    if body.prefetch_enabled is not None: gs.prefetch_enabled = body.prefetch_enabled
    
    db.commit()
    return {
        "lm_url": gs.lm_url,
        "lm_model": gs.lm_model,
        "target_language": gs.target_language,
        "prefetch_enabled": gs.prefetch_enabled
    }

@router.get("/threads/{thread_id}/context")
def get_thread_context(thread_id: int, db: Session = Depends(get_db)):
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
    return {"thread_context": thread.thread_context or ""}

@router.post("/threads/{thread_id}/context")
def update_thread_context(thread_id: int, body: ContextUpdate, db: Session = Depends(get_db)):
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
    thread.thread_context = body.context
    db.commit()
    return {"thread_context": thread.thread_context}

@router.post("/threads/{thread_id}/extract-context")
async def extract_thread_context(thread_id: int, req: ExtractRequest, db: Session = Depends(get_db)):
    """Analyze chapter text to extract key terms (names, locations, etc)."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order)
    chapter = db.execute(ch_stmt).scalars().first()
    if not chapter or not chapter.content_original:
        return {"terms": []}

    # Use a larger sample for extraction if available
    text_sample = " ".join(chapter.content_original.split()[:3000])
    
    prompt = (
        "You are an expert literary analyst specializing in Chinese web novels. "
        "Your task is to identify and extract key proper nouns from the text provided. "
        "Focus on: Character Names, Locations, Special Items, Cultivation Levels/Abilities, and Organizations. "
        "\n\nRules:\n"
        "1. Identify the term in its original language (Chinese).\n"
        "2. Provide a short description or context for each term.\n"
        "3. Format the output as a JSON list: [{\"original_term\": \"...\", \"notes\": \"...\"}].\n"
        "4. If JSON is not possible, list them as 'Term: Description' on each line.\n"
        "5. Do NOT include common words, only significant proper nouns."
    )
    
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    ai_url = req.lm_url or (gs.lm_url if gs else "http://localhost:1234")
    ai = AIProvider(ai_url)
    
    payload = {
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text_sample},
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
                return {"terms": terms}
            except:
                pass

        # 2. Fallback to manual line parsing
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
                        "notes": parts[1].strip()
                    })
            elif line and 1 < len(line) < 30: # Potential name on its own line
                # Basic check to avoid common prose lines
                if not any(stop in line.lower() for stop in ["the ", "a ", "is ", "in "]):
                    manual_terms.append({
                        "original_term": line,
                        "notes": "Detected proper noun"
                    })
        
        return {"terms": manual_terms}

    except Exception as e:
        raise HTTPException(502, str(e))
