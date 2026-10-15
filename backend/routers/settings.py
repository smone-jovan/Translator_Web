from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
import json
from database import get_db, GlobalSetting, Thread
from services.ai.secrets import load_secrets, save_secrets, mask_secret, is_masked_secret, resolve_masked_keys

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
    load_mode: str | None = None
    polish_mode: str | None = None
    polish_soft_limit: int | None = None
    max_context_terms: int | None = None
    extract_chapter_count: int | None = None
    extract_sample_size: int | None = None
    always_hide_thoughts: int | None = None
    chapter_token_cap_enabled: int | None = None
    chapter_token_cap: int | None = None
    translation_mode: str | None = None
    display_mode: str | None = None
    scraper_concurrency: int | None = None
    novalpie_auth_enabled: int | None = None
    novalpie_cookie: str | None = None

    # Cloud LLM & API Keys Settings (ADR-029)
    llm_provider: str | None = None
    openai_url: str | None = None
    openai_model: str | None = None
    gemini_model: str | None = None
    openrouter_model: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    # Multiple API keys
    openai_api_keys: list[str] | None = None
    openai_active_key_index: int | None = None
    gemini_api_keys: list[str] | None = None
    gemini_active_key_index: int | None = None
    openrouter_api_keys: list[str] | None = None
    openrouter_active_key_index: int | None = None
    # Ghost Mode PIN authentication
    ghost_pin: str | None = None

@router.get("/settings")
@router.get("/global-context")
def get_global_context(db: Session = Depends(get_db)):
    stmt = select(GlobalSetting)
    gs = db.execute(stmt).scalar_one_or_none()

    secrets = load_secrets()

    return {
        "global_context": gs.global_context if gs else "",
        "lm_url": gs.lm_url if gs else "http://localhost:1234",
        "lm_model": gs.lm_model if gs else None,
        "target_language": gs.target_language if gs else "Indonesian",
        "prefetch_enabled": gs.prefetch_enabled if gs else 0,
        "prefetch_count": gs.prefetch_count if gs else 2,
        "prefetch_mode": gs.prefetch_mode if gs else "soft",
        "load_mode": gs.prefetch_mode if gs else "soft",
        "polish_mode": gs.polish_mode if gs else "soft",
        "polish_soft_limit": gs.polish_soft_limit if gs else 100,
        "max_context_terms": (gs.max_context_terms if (gs and gs.max_context_terms) else 150),
        "extract_chapter_count": gs.extract_chapter_count if gs else 25,
        "extract_sample_size": gs.extract_sample_size if gs else 1000,
        "always_hide_thoughts": gs.always_hide_thoughts if gs is not None and gs.always_hide_thoughts is not None else 1,
        "chapter_token_cap_enabled": gs.chapter_token_cap_enabled if gs is not None and gs.chapter_token_cap_enabled is not None else 1,
        "chapter_token_cap": gs.chapter_token_cap if gs else 22000,
        "translation_mode": gs.translation_mode if gs else "quality",
        "display_mode": getattr(gs, "display_mode", "translated") or "translated",

        "llm_provider": gs.llm_provider if gs else "lm_studio",
        "openai_url": gs.openai_url if gs else "https://api.openai.com/v1",
        "openai_model": gs.openai_model if gs else "gpt-4o",
        "gemini_model": gs.gemini_model if gs else "gemini-2.5-flash",
        "openrouter_model": gs.openrouter_model if gs else "deepseek/deepseek-chat",
        "openai_api_key": mask_secret(secrets.get("openai_api_key", "")),
        "gemini_api_key": mask_secret(secrets.get("gemini_api_key", "")),
        "openrouter_api_key": mask_secret(secrets.get("openrouter_api_key", "")),
        "openai_api_keys": [mask_secret(k) for k in json.loads(gs.openai_api_keys)] if gs and gs.openai_api_keys else [],
        "openai_active_key_index": gs.openai_active_key_index if gs else 0,
        "gemini_api_keys": [mask_secret(k) for k in json.loads(gs.gemini_api_keys)] if gs and gs.gemini_api_keys else [],
        "gemini_active_key_index": gs.gemini_active_key_index if gs else 0,
        "openrouter_api_keys": [mask_secret(k) for k in json.loads(gs.openrouter_api_keys)] if gs and gs.openrouter_api_keys else [],
        "openrouter_active_key_index": gs.openrouter_active_key_index if gs else 0,
        "ghost_pin": mask_secret(gs.ghost_pin if gs else "03697"),
        "scraper_concurrency": getattr(gs, "scraper_concurrency", 2) if gs else 2,
        "novalpie_auth_enabled": getattr(gs, "novalpie_auth_enabled", 0) if gs else 0,
        "novalpie_cookie": mask_secret(secrets.get("novalpie_cookie", "") or getattr(gs, "novalpie_cookie", "") or ""),
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

    limit_changed = req.max_context_terms is not None and req.max_context_terms != gs.max_context_terms

    if req.lm_url is not None: gs.lm_url = req.lm_url
    if req.lm_model is not None: gs.lm_model = req.lm_model
    if req.target_language is not None: gs.target_language = req.target_language
    if req.prefetch_enabled is not None: gs.prefetch_enabled = req.prefetch_enabled
    if req.prefetch_count is not None: gs.prefetch_count = req.prefetch_count
    if req.prefetch_mode is not None: gs.prefetch_mode = req.prefetch_mode
    if req.load_mode is not None: gs.prefetch_mode = req.load_mode
    if req.polish_mode is not None: gs.polish_mode = req.polish_mode
    if req.polish_soft_limit is not None: gs.polish_soft_limit = req.polish_soft_limit
    if req.max_context_terms is not None: gs.max_context_terms = req.max_context_terms
    if req.extract_chapter_count is not None: gs.extract_chapter_count = req.extract_chapter_count
    if req.extract_sample_size is not None: gs.extract_sample_size = req.extract_sample_size
    if req.always_hide_thoughts is not None: gs.always_hide_thoughts = req.always_hide_thoughts
    if req.chapter_token_cap_enabled is not None: gs.chapter_token_cap_enabled = req.chapter_token_cap_enabled
    if req.chapter_token_cap is not None: gs.chapter_token_cap = req.chapter_token_cap
    if req.translation_mode is not None: gs.translation_mode = req.translation_mode
    if req.display_mode is not None: gs.display_mode = req.display_mode
    if req.scraper_concurrency is not None: gs.scraper_concurrency = max(1, min(5, req.scraper_concurrency))
    if req.novalpie_auth_enabled is not None: gs.novalpie_auth_enabled = req.novalpie_auth_enabled
    gs.novalpie_cookie = ""

    if req.llm_provider is not None: gs.llm_provider = req.llm_provider
    if req.openai_url is not None: gs.openai_url = req.openai_url
    if req.openai_model is not None: gs.openai_model = req.openai_model
    if req.gemini_model is not None: gs.gemini_model = req.gemini_model
    if req.openrouter_model is not None: gs.openrouter_model = req.openrouter_model
    if req.ghost_pin is not None and not is_masked_secret(req.ghost_pin):
        gs.ghost_pin = req.ghost_pin

    real_openai = req.openai_api_key if (req.openai_api_key is not None and not is_masked_secret(req.openai_api_key)) else None
    real_gemini = req.gemini_api_key if (req.gemini_api_key is not None and not is_masked_secret(req.gemini_api_key)) else None
    real_openrouter = req.openrouter_api_key if (req.openrouter_api_key is not None and not is_masked_secret(req.openrouter_api_key)) else None
    real_cookie = req.novalpie_cookie.strip() if (req.novalpie_cookie is not None and not is_masked_secret(req.novalpie_cookie)) else None

    if real_openai is not None or real_gemini is not None or real_openrouter is not None or real_cookie is not None:
        save_secrets(
            openai_api_key=real_openai,
            gemini_api_key=real_gemini,
            openrouter_api_key=real_openrouter,
            novalpie_cookie=real_cookie,
        )
        gs.novalpie_cookie = ""

    if req.openai_api_keys is not None:
        try:
            existing_openai = json.loads(gs.openai_api_keys) if gs.openai_api_keys else []
        except Exception:
            existing_openai = []
        gs.openai_api_keys = json.dumps(resolve_masked_keys(req.openai_api_keys, existing_openai))
    if req.openai_active_key_index is not None:
        gs.openai_active_key_index = req.openai_active_key_index
    if req.gemini_api_keys is not None:
        try:
            existing_gemini = json.loads(gs.gemini_api_keys) if gs.gemini_api_keys else []
        except Exception:
            existing_gemini = []
        gs.gemini_api_keys = json.dumps(resolve_masked_keys(req.gemini_api_keys, existing_gemini))
    if req.gemini_active_key_index is not None:
        gs.gemini_active_key_index = req.gemini_active_key_index
    if req.openrouter_api_keys is not None:
        try:
            existing_openrouter = json.loads(gs.openrouter_api_keys) if gs.openrouter_api_keys else []
        except Exception:
            existing_openrouter = []
        gs.openrouter_api_keys = json.dumps(resolve_masked_keys(req.openrouter_api_keys, existing_openrouter))
    if req.openrouter_active_key_index is not None:
        gs.openrouter_active_key_index = req.openrouter_active_key_index

    db.commit()

    # Live-sync all threads' lorebook active/archived status when max_context_terms changes
    if limit_changed or req.max_context_terms is not None:
        try:
            from routers.lorebook import enforce_context_limit
            thread_ids = db.execute(select(Thread.id)).scalars().all()
            for t_id in thread_ids:
                enforce_context_limit(t_id, db)
        except Exception as e:
            print(f"[SETTINGS] Failed to re-enforce lorebook limits: {e}")

    return {"status": "ok"}
