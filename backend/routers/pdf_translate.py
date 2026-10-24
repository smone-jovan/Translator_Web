"""
POST /api/translate/pdf — translate an uploaded PDF page by page with an Index-Translate model.

Pages with a text layer go through the text prompt; scans and comics are rendered to PNG and go
through the image prompt. Progress is streamed as NDJSON; nothing is stored on the server.
"""
import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import GlobalSetting, get_db
from routers.image_translate import resolve_target_lang, safe_provider_error, translate_image_data_url
from services.translation_guard import NonTranslationError
from services.ai.chunking import split_into_chunks
from services.ai.factory import AIProviderFactory
from services.ai.index_translate import build_index_translate_messages, is_index_translate_model
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.context_engine import ContextEngine
from services.pdf_pages import (
    MAX_PDF_BYTES,
    PdfRejectedError,
    PdfTooLargeError,
    classify_page,
    open_pdf,
    page_text,
    render_page_png_data_url,
)

router = APIRouter(prefix="/api", tags=["Translation"])

UPLOAD_READ_BYTES = 1024 * 1024
TEXT_CHUNK_CHARS = 2500


async def _read_limited(upload: UploadFile) -> bytes:
    """Read the upload in pieces and stop as soon as it exceeds the cap (never buffer an unbounded body)."""
    data = bytearray()
    while piece := await upload.read(UPLOAD_READ_BYTES):
        data.extend(piece)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(413, f"PDF is too large (max {MAX_PDF_BYTES // (1024 * 1024)} MB)")
    return bytes(data)


async def _translate_text(provider, gs, text: str, target_lang: str) -> str:
    temperature = getattr(provider, "translation_temperature", 0.0)
    hide_thoughts = bool(getattr(gs, "always_hide_thoughts", 1) if gs else 1)
    parts = []
    for chunk in split_into_chunks(text, TEXT_CHUNK_CHARS):
        reply = await provider.chat_completion(
            messages=build_index_translate_messages(chunk, target_lang), temperature=temperature
        )
        parts.append(ContextEngine.clean_final_translation(reply, always_hide_thoughts=hide_thoughts))
    return "\n\n".join(parts)


def _line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


@router.post("/translate/pdf")
async def translate_pdf(
    request: Request,
    file: UploadFile = File(...),
    model: str | None = Form(None),
    target_lang: str = Form("Indonesian"),
    lm_url: str | None = Form(None),
    db: Session = Depends(get_db),
):
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    model_name = resolve_active_model(gs, model)
    if not is_index_translate_model(model_name):
        raise HTTPException(400, "PDF translation needs an Index-Translate model (it ships a vision projector).")

    try:
        doc = open_pdf(await _read_limited(file))
    except PdfTooLargeError as e:
        raise HTTPException(413, str(e))
    except PdfRejectedError as e:
        raise HTTPException(400, str(e))

    lang = resolve_target_lang(gs, target_lang)
    provider = AIProviderFactory.get_provider(
        base_url=resolve_active_base_url(gs, lm_url), model=model_name, db_session=db
    )

    async def stream() -> AsyncIterator[str]:
        try:
            yield _line({"type": "start", "pages": len(doc)})
            for index in range(len(doc)):
                if await request.is_disconnected():
                    return
                try:
                    page = doc[index]
                    text = page_text(page)
                    mode = classify_page(text)
                    if mode == "text":
                        translation = await _translate_text(provider, gs, text, lang)
                    else:
                        data_url = await asyncio.to_thread(render_page_png_data_url, page)
                        translation = await translate_image_data_url(provider, gs, data_url, lang)
                except NonTranslationError as e:
                    yield _line({"type": "page_error", "index": index, "error": e.message, "reason": e.reason})
                    continue
                except Exception as e:
                    yield _line({"type": "page_error", "index": index, "error": safe_provider_error(e, "Page translation")})
                    continue
                yield _line({"type": "page", "index": index, "mode": mode, "translation": translation})
            yield _line({"type": "done", "model_used": model_name})
        finally:
            doc.close()

    return StreamingResponse(stream(), media_type="application/x-ndjson")
