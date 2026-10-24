"""
Folders of images (manga chapters, scans) for Index-Translate.

POST /api/translate/images           — translate every image, streamed as NDJSON (same events as the PDF route).
POST /api/translate/images/export-pdf — build a PDF (image page + translation page per image) from the same files.

Nothing is stored on the server and uploaded file names are never used as paths.
"""
import asyncio
import json
from typing import AsyncIterator, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import GlobalSetting, get_db
from routers.image_translate import resolve_target_lang, safe_provider_error, translate_image_data_url
from routers.pdf_translate import UPLOAD_READ_BYTES, _line
from services.ai.factory import AIProviderFactory
from services.ai.index_translate import MAX_IMAGE_BYTES, is_index_translate_model
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.manga_detector import DetectorUnavailableError, detect_text_boxes, load_detector
from services.manga_overlay import Box
from services.manga_pipeline import translate_page_boxes
from services.image_batch import (
    ImageRejectedError,
    ImageTooLargeError,
    build_translated_pdf,
    prepare_image_data_url,
)

router = APIRouter(prefix="/api", tags=["Translation"])

MAX_IMAGES = 60
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_TRANSLATION_CHARS = 50_000
MAX_BOXES_PER_PAGE = 100
MAX_BOX_TEXT_CHARS = 2000
MAX_COORDINATE = 100_000
_BOX_COORDS = ("x0", "y0", "x1", "y1")


async def _read_images(uploads: List[UploadFile]) -> List[bytes]:
    """Read every upload with a per-file and a total cap, so no request can buffer an unbounded body."""
    if not uploads:
        raise HTTPException(400, "No images were uploaded")
    if len(uploads) > MAX_IMAGES:
        raise HTTPException(413, f"Too many images (max {MAX_IMAGES})")

    payloads: List[bytes] = []
    total = 0
    for upload in uploads:
        data = bytearray()
        while len(data) <= MAX_IMAGE_BYTES and (piece := await upload.read(UPLOAD_READ_BYTES)):
            data.extend(piece)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(413, f"Upload is too large (max {MAX_TOTAL_BYTES // (1024 * 1024)} MB in total)")
        payloads.append(bytes(data))
    return payloads


def _parse_translations(raw: str, expected: int) -> List[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "translations must be a JSON array of strings") from None
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise HTTPException(400, "translations must be a JSON array of strings")
    if len(parsed) != expected:
        raise HTTPException(400, "translations must have one entry per image")
    if any(len(item) > MAX_TRANSLATION_CHARS for item in parsed):
        raise HTTPException(413, "A translation is too long")
    return parsed


def _parse_boxes(raw: str, expected: int) -> List[List[Box]]:
    """Client-supplied overlay boxes are untrusted: strict types, bounded counts, bounded sizes."""
    bad = HTTPException(400, "boxes must be a JSON array (one list per image) of {x0,y0,x1,y1,text}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise bad from None
    if not isinstance(parsed, list) or len(parsed) != expected:
        raise bad
    pages: List[List[Box]] = []
    for page in parsed:
        if not isinstance(page, list) or len(page) > MAX_BOXES_PER_PAGE:
            raise bad
        boxes = []
        for item in page:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                raise bad
            coords = [item.get(name) for name in _BOX_COORDS]
            if not all(type(v) is int and 0 <= v <= MAX_COORDINATE for v in coords):
                raise bad
            if len(item["text"]) > MAX_BOX_TEXT_CHARS:
                raise bad
            boxes.append(Box(*coords, item["text"]))
        pages.append(boxes)
    return pages


@router.post("/translate/images")
async def translate_images(
    request: Request,
    files: List[UploadFile] = File(...),
    model: str | None = Form(None),
    target_lang: str = Form("Indonesian"),
    lm_url: str | None = Form(None),
    overlay: bool = Form(False),
    db: Session = Depends(get_db),
):
    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    model_name = resolve_active_model(gs, model)
    if not is_index_translate_model(model_name):
        raise HTTPException(400, "Image translation needs an Index-Translate model (it ships a vision projector).")

    if overlay:
        try:
            await asyncio.to_thread(load_detector)
        except DetectorUnavailableError:
            raise HTTPException(400, "Text detector model is not installed (see ADR-132 to download it).")

    payloads = await _read_images(files)
    lang = resolve_target_lang(gs, target_lang)
    provider = AIProviderFactory.get_provider(
        base_url=resolve_active_base_url(gs, lm_url), model=model_name, db_session=db
    )

    async def translate_crop(data_url: str) -> str:
        return await translate_image_data_url(provider, gs, data_url, lang)

    async def translate_page(payload: bytes) -> dict:
        if overlay:
            if len(payload) > MAX_IMAGE_BYTES:
                raise ImageTooLargeError(f"Image is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB)")
            boxes = [b for b in await translate_page_boxes(payload, translate_crop, detector=detect_text_boxes) if b.text]
            if boxes:
                return {
                    "mode": "overlay",
                    "translation": "\n\n".join(b.text for b in boxes),
                    "boxes": [{"x0": b.x0, "y0": b.y0, "x1": b.x1, "y1": b.y1, "text": b.text} for b in boxes],
                }
        data_url = await asyncio.to_thread(prepare_image_data_url, payload)
        return {"mode": "image", "translation": await translate_image_data_url(provider, gs, data_url, lang)}

    async def stream() -> AsyncIterator[str]:
        yield _line({"type": "start", "pages": len(payloads)})
        for index, payload in enumerate(payloads):
            if await request.is_disconnected():
                return
            try:
                page = await translate_page(payload)
            except ValueError as e:  # unreadable, too large or not a PNG/JPEG
                yield _line({"type": "page_error", "index": index, "error": str(e)})
                continue
            except Exception as e:
                yield _line({"type": "page_error", "index": index, "error": safe_provider_error(e, "Page translation")})
                continue
            yield _line({"type": "page", "index": index, **page})
        yield _line({"type": "done", "model_used": model_name})

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.post("/translate/images/export-pdf")
async def export_images_pdf(
    files: List[UploadFile] = File(...),
    translations: str = Form(...),
    boxes: Optional[str] = Form(None),
    include_text_pages: bool = Form(True),
):
    payloads = await _read_images(files)
    texts = _parse_translations(translations, len(payloads))
    overlays = _parse_boxes(boxes, len(payloads)) if boxes else None
    try:
        for payload in payloads:
            await asyncio.to_thread(prepare_image_data_url, payload)
        pdf = await asyncio.to_thread(build_translated_pdf, payloads, texts, overlays, include_text_pages)
    except ImageTooLargeError as e:
        raise HTTPException(413, str(e))
    except ImageRejectedError as e:
        raise HTTPException(400, str(e))

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="translated-images.pdf"'},
    )
