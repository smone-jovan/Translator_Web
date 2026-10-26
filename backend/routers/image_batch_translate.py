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
from routers.image_translate import (
    resolve_target_lang,
    safe_provider_error,
    translate_image_checked,
    translate_image_data_url,
)
from routers.pdf_translate import UPLOAD_READ_BYTES, _line
from services.ai.factory import AIProviderFactory
from services.ai.index_translate import MAX_IMAGE_BYTES, is_index_translate_model
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.image_zip import (
    MAX_IMAGES,
    MAX_TOTAL_BYTES,
    ExtractedImage,
    ZipRejectedError,
    ZipTooLargeError,
    display_name,
    extract_images,
    looks_like_zip,
)
from services.image_normalize import normalize_image, normalized_name
from services.translation_guard import NonTranslationError
from services.manga_detector import DetectorUnavailableError, detect_text_boxes, load_detector
from services.lm_slots import detect_parallel
from services.manga_fallback import translate_crop_fallback
from services.manga_overlay import Box
from services.manga_pipeline import MAX_BOX_TEXT_CHARS, translate_page_boxes
from services.image_batch import (
    ImageRejectedError,
    ImageTooLargeError,
    build_translated_pdf,
    prepare_image_data_url,
)

router = APIRouter(prefix="/api", tags=["Translation"])

MAX_TRANSLATION_CHARS = 50_000
MAX_BOXES_PER_PAGE = 100
MAX_COORDINATE = 100_000
_BOX_COORDS = ("x0", "y0", "x1", "y1")


def _normalize(image: ExtractedImage) -> ExtractedImage:
    """WebP pages become PNG/JPEG here so everything downstream only sees those; a bad one stays as is
    and is reported per page (or rejected on export) by prepare_image_data_url."""
    try:
        data = normalize_image(image.data)
    except ImageRejectedError:
        return image
    except ImageTooLargeError:
        return ExtractedImage(image.name, image.data[: MAX_IMAGE_BYTES + 1])
    return ExtractedImage(normalized_name(image.name, data), data)


async def _normalize_all(images: List[ExtractedImage]) -> List[ExtractedImage]:
    return [await asyncio.to_thread(_normalize, image) for image in images]


async def _read_images(uploads: List[UploadFile]) -> List[ExtractedImage]:
    """Read the uploads (capped in total, never an unbounded body); a single ZIP is expanded in memory."""
    if not uploads:
        raise HTTPException(400, "No images were uploaded")
    if len(uploads) > MAX_IMAGES:
        raise HTTPException(413, f"Too many images (max {MAX_IMAGES})")

    received: List[ExtractedImage] = []
    total = 0
    for number, upload in enumerate(uploads, start=1):
        data = bytearray()
        while piece := await upload.read(UPLOAD_READ_BYTES):
            data.extend(piece)
            total += len(piece)
            if total > MAX_TOTAL_BYTES:
                raise HTTPException(413, f"Upload is too large (max {MAX_TOTAL_BYTES // (1024 * 1024)} MB in total)")
        received.append(ExtractedImage(display_name(upload.filename or "") or f"image{number}", bytes(data)))

    if any(looks_like_zip(item.data) for item in received):
        if len(received) != 1:
            raise HTTPException(400, "Upload either one ZIP file or image files, not both")
        try:
            return await _normalize_all(extract_images(received[0].data))
        except ZipTooLargeError as e:
            raise HTTPException(413, str(e))
        except ZipRejectedError as e:
            raise HTTPException(400, str(e))

    # A single image over the cap is reported per page (page_error) instead of failing the whole batch.
    return await _normalize_all(
        [ExtractedImage(item.name, item.data[: MAX_IMAGE_BYTES + 1]) for item in received]
    )


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
    fallback_model: str | None = Form(None),
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

    images = await _read_images(files)
    payloads = [image.data for image in images]
    lang = resolve_target_lang(gs, target_lang)
    provider = AIProviderFactory.get_provider(
        base_url=resolve_active_base_url(gs, lm_url), model=model_name, db_session=db
    )

    async def translate_crop(data_url: str) -> str:
        return await translate_image_data_url(provider, gs, data_url, lang)

    fallback_crop = None
    if overlay and fallback_model and fallback_model.strip():
        fallback_provider = AIProviderFactory.get_provider(
            base_url=resolve_active_base_url(gs, lm_url), model=fallback_model.strip(), db_session=db
        )

        async def fallback_crop(data_url: str) -> str:
            return await translate_crop_fallback(fallback_provider, data_url, lang)

    concurrency_probe = None
    if overlay and getattr(gs, "llm_provider", "lm_studio") == "lm_studio":
        lm_base_url = resolve_active_base_url(gs, lm_url)

        async def concurrency_probe() -> int:
            return await detect_parallel(lm_base_url, model_name)

    async def translate_page(payload: bytes) -> dict:
        if overlay:
            if len(payload) > MAX_IMAGE_BYTES:
                raise ImageTooLargeError(f"Image is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB)")
            boxes = [b for b in await translate_page_boxes(payload, translate_crop, detector=detect_text_boxes, fallback_crop=fallback_crop, concurrency_probe=concurrency_probe) if b.text]
            if not boxes:  # overlay was asked for: never fall back to sending the whole page to the model
                raise NonTranslationError("no_text")
            return {
                "mode": "overlay",
                "translation": "\n\n".join(b.text for b in boxes),
                "boxes": [{"x0": b.x0, "y0": b.y0, "x1": b.x1, "y1": b.y1, "text": b.text} for b in boxes],
            }
        data_url = await asyncio.to_thread(prepare_image_data_url, payload)
        result = await translate_image_checked(provider, gs, data_url, lang)
        return {"mode": "image", "translation": result.text, **({"truncated": True} if result.truncated else {})}

    async def stream() -> AsyncIterator[str]:
        yield _line({"type": "start", "pages": len(payloads), "names": [image.name for image in images]})
        for index, payload in enumerate(payloads):
            if await request.is_disconnected():
                return
            try:
                page = await translate_page(payload)
            except NonTranslationError as e:
                yield _line({"type": "page_error", "index": index, "error": e.message, "reason": e.reason})
                continue
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
    payloads = [image.data for image in await _read_images(files)]
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
