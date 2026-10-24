"""
POST /api/translate/image — translate the text inside an image with an Index-Translate vision model.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import GlobalSetting, get_db
from services.ai.factory import AIProviderFactory
from services.ai.index_translate import (
    IMAGE_MAX_TOKENS,
    ImageTooLargeError,
    build_index_translate_image_messages,
    is_index_translate_model,
    validate_image_data_url,
)
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.context_engine import ContextEngine

router = APIRouter(prefix="/api", tags=["Translation"])


class ImageTranslateRequest(BaseModel):
    image_data_url: str
    model: str | None = None
    target_lang: str = "Indonesian"
    lm_url: str | None = None


class ImageTranslateResponse(BaseModel):
    translation: str
    model_used: str


@router.post("/translate/image", response_model=ImageTranslateResponse)
async def translate_image(req: ImageTranslateRequest, db: Session = Depends(get_db)):
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    model = resolve_active_model(gs, req.model)
    if not is_index_translate_model(model):
        raise HTTPException(400, "Image translation needs an Index-Translate model (it ships a vision projector).")

    try:
        image_data_url = validate_image_data_url(req.image_data_url)
    except ImageTooLargeError as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    target_lang = resolve_target_lang(gs, req.target_lang)
    provider = AIProviderFactory.get_provider(
        base_url=resolve_active_base_url(gs, req.lm_url), model=model, db_session=db
    )

    try:
        translation = await translate_image_data_url(provider, gs, image_data_url, target_lang)
    except Exception as e:
        raise HTTPException(502, safe_provider_error(e, "Image translation"))

    return ImageTranslateResponse(translation=translation, model_used=model)


def resolve_target_lang(gs, requested: str) -> str:
    return requested if requested != "Indonesian" else (gs.target_language if gs else "Indonesian")


def safe_provider_error(error: Exception, label: str) -> str:
    """Log the full error server-side, but give the client a message that leaks no internals."""
    print(f"[ERROR] {label} failed: {error}")
    if "connection" in str(error).lower() or "timeout" in str(error).lower():
        return "AI provider connection failed. Is the LLM server running?"
    return f"{label} request failed. Check server logs for details."


async def translate_image_data_url(provider, gs, image_data_url: str, target_lang: str) -> str:
    reply = await provider.chat_completion(
        messages=build_index_translate_image_messages(image_data_url, target_lang),
        temperature=getattr(provider, "translation_temperature", 0.3),
        max_tokens=IMAGE_MAX_TOKENS,
    )
    always_hide_thoughts = getattr(gs, "always_hide_thoughts", 1) if gs else 1
    return ContextEngine.clean_final_translation(reply, always_hide_thoughts=bool(always_hide_thoughts))
