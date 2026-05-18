from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db, GlobalSetting
from services.ai.secrets import load_secrets, save_secrets

router = APIRouter(prefix="/api", tags=["Settings"])

class ContextUpdate(BaseModel):
    context: str

class GlobalSettingsUpdate(BaseModel):
    lm_url: str | None = None
    lm_model: str | None = None
    target_language: str | None = None
    prefetch_enabled: int | None = None
    prefetch_count: int | None = None
    prefetch_mode: str | None = None
    polish_mode: str | None = None
    polish_soft_limit: int | None = None
    max_context_terms: int | None = None
    extract_chapter_count: int | None = None
    extract_sample_size: int | None = None
    always_hide_thoughts: int | None = None
    chapter_token_cap_enabled: int | None = None
    chapter_token_cap: int | None = None
    
    # Cloud LLM & API Keys Settings (ADR-029)
    llm_provider: str | None = None
    openai_url: str | None = None
    openai_model: str | None = None
    gemini_model: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None

@router.get("/global-context")
def get_global_context(db: Session = Depends(get_db)):
    stmt = select(GlobalSetting)
    gs = db.execute(stmt).scalar_one_or_none()
    
    # Load keys securely from ignored .env file
    secrets = load_secrets()
    
    return {
        "global_context": gs.global_context if gs else "",
        "lm_url": gs.lm_url if gs else "http://localhost:1234",
        "lm_model": gs.lm_model if gs else None,
        "target_language": gs.target_language if gs else "Indonesian",
        "prefetch_enabled": gs.prefetch_enabled if gs else 0,
        "prefetch_count": gs.prefetch_count if gs else 2,
        "prefetch_mode": gs.prefetch_mode if gs else "soft",
        "polish_mode": gs.polish_mode if gs else "soft",
        "polish_soft_limit": gs.polish_soft_limit if gs else 100,
        "max_context_terms": gs.max_context_terms if gs else 50,
        "extract_chapter_count": gs.extract_chapter_count if gs else 25,
        "extract_sample_size": gs.extract_sample_size if gs else 1000,
        "always_hide_thoughts": gs.always_hide_thoughts if gs else 1,
        "chapter_token_cap_enabled": gs.chapter_token_cap_enabled if gs else 1,
        "chapter_token_cap": gs.chapter_token_cap if gs else 22000,
        
        # New Settings Fields
        "llm_provider": gs.llm_provider if gs else "lm_studio",
        "openai_url": gs.openai_url if gs else "https://api.openai.com/v1",
        "openai_model": gs.openai_model if gs else "gpt-4o",
        "gemini_model": gs.gemini_model if gs else "gemini-2.5-flash",
        "openai_api_key": secrets.get("openai_api_key", ""),
        "gemini_api_key": secrets.get("gemini_api_key", "")
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
    if req.polish_mode is not None: gs.polish_mode = req.polish_mode
    if req.polish_soft_limit is not None: gs.polish_soft_limit = req.polish_soft_limit
    if req.max_context_terms is not None: gs.max_context_terms = req.max_context_terms
    if req.extract_chapter_count is not None: gs.extract_chapter_count = req.extract_chapter_count
    if req.extract_sample_size is not None: gs.extract_sample_size = req.extract_sample_size
    if req.always_hide_thoughts is not None: gs.always_hide_thoughts = req.always_hide_thoughts
    if req.chapter_token_cap_enabled is not None: gs.chapter_token_cap_enabled = req.chapter_token_cap_enabled
    if req.chapter_token_cap is not None: gs.chapter_token_cap = req.chapter_token_cap
    
    # Cloud LLM & API Keys Settings (ADR-029)
    if req.llm_provider is not None: gs.llm_provider = req.llm_provider
    if req.openai_url is not None: gs.openai_url = req.openai_url
    if req.openai_model is not None: gs.openai_model = req.openai_model
    if req.gemini_model is not None: gs.gemini_model = req.gemini_model
    
    # Save secret keys safely to .env
    if req.openai_api_key is not None or req.gemini_api_key is not None:
        save_secrets(openai_api_key=req.openai_api_key, gemini_api_key=req.gemini_api_key)
    
    db.commit()
    return {"status": "ok"}
