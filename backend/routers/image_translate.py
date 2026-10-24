"""
POST /api/translate/image — translate the text inside an image with an Index-Translate vision model.
"""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import GlobalSetting, get_db
from services.ai.base import Completion
from services.ai.factory import AIProviderFactory
from services.ai.index_translate import (
    IMAGE_MAX_TOKENS,
    IMAGE_PENALTY_PARAM,
    IMAGE_REPEAT_PENALTY,
    IMAGE_RETRY_REPEAT_PENALTY,
    ImageTooLargeError,
    build_index_translate_image_messages,
    is_index_translate_model,
    validate_image_data_url,
)
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.context_engine import ContextEngine
from services.translation_guard import NonTranslationError, classify_image_reply

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
    except NonTranslationError as e:
        raise HTTPException(422, e.message)
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


@dataclass(frozen=True)
class ImageTranslation:
    text: str
    truncated: bool = False


async def _complete_image(provider, messages, penalty: float) -> Completion:
    """One vision request. Providers with `chat_completion_detailed` also report finish_reason and get the repeat
    penalty; if the server rejects that extra parameter the request is repeated without it."""
    temperature = getattr(provider, "translation_temperature", 0.3)
    detailed = getattr(provider, "chat_completion_detailed", None)
    if detailed is None:
        text = await provider.chat_completion(messages=messages, temperature=temperature, max_tokens=IMAGE_MAX_TOKENS)
        return Completion(text)
    try:
        return await detailed(messages, temperature, IMAGE_MAX_TOKENS, {IMAGE_PENALTY_PARAM: penalty})
    except Exception as e:
        print(f"[WARN] Image request with {IMAGE_PENALTY_PARAM} failed, retrying without it: {e}")
        return await detailed(messages, temperature, IMAGE_MAX_TOKENS, None)


async def translate_image_checked(provider, gs, image_data_url: str, target_lang: str) -> ImageTranslation:
    """Translate one image and refuse replies that are not translations (see services/translation_guard.py).

    A looping reply is retried once with a stronger repeat penalty; refusals and descriptions are not retried.
    """
    messages = build_index_translate_image_messages(image_data_url, target_lang)
    hide_thoughts = bool(getattr(gs, "always_hide_thoughts", 1) if gs else 1)
    verdict = None
    for penalty in (IMAGE_REPEAT_PENALTY, IMAGE_RETRY_REPEAT_PENALTY):
        completion = await _complete_image(provider, messages, penalty)
        text = ContextEngine.clean_final_translation(completion.text, always_hide_thoughts=hide_thoughts)
        verdict = classify_image_reply(text, completion.finish_reason)
        if verdict.ok:
            return ImageTranslation(text, truncated=verdict.kind == "truncated")
        if verdict.kind != "loop":
            break
    raise NonTranslationError(verdict.kind)


async def translate_image_data_url(provider, gs, image_data_url: str, target_lang: str) -> str:
    return (await translate_image_checked(provider, gs, image_data_url, target_lang)).text
