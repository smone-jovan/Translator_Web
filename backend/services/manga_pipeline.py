"""
One manga page -> translated text boxes: detect text boxes, crop each (with a small margin), and ask the
vision model to translate the crop. The model call is injected so this module stays free of providers,
routers and the database.
"""
import asyncio
import base64
import io
from typing import Awaitable, Callable, List, Optional

from PIL import Image

from services.ai.index_translate import validate_image_data_url
from services.manga_detector import detect_text_boxes
from services.lm_slots import resolve_concurrency
from services.manga_overlay import Box, open_rgb
from services.translation_guard import NonTranslationError

CROP_MARGIN_PX = 12  # measured on a real chapter: wider margin and less upscaling stopped the 2B model looping
MIN_CROP_EDGE_PX = 256
MAX_CROP_EDGE_PX = 2048
MAX_CONSECUTIVE_FAILURES = 3
CROP_CONCURRENCY = 4  # matches an LM Studio model loaded with 4 parallel slots; a single slot just queues them
MAX_BOX_TEXT_CHARS = 2000  # the PDF export rejects longer box text; longer output is a runaway reply

TranslateCrop = Callable[[str], Awaitable[str]]


def _crop_data_url(image: Image.Image, box) -> str:
    crop = image.crop(
        (
            max(0, box.x0 - CROP_MARGIN_PX),
            max(0, box.y0 - CROP_MARGIN_PX),
            min(image.width, box.x1 + CROP_MARGIN_PX),
            min(image.height, box.y1 + CROP_MARGIN_PX),
        )
    )
    longest = max(crop.size)
    target = min(max(longest, MIN_CROP_EDGE_PX), MAX_CROP_EDGE_PX)
    if target != longest:
        scale = target / longest
        crop = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.LANCZOS)
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG")
    return validate_image_data_url(f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}")


async def translate_page_boxes(
    image_bytes: bytes,
    translate_crop: TranslateCrop,
    *,
    detector=detect_text_boxes,
    fallback_crop: Optional[TranslateCrop] = None,
    concurrency_probe: Optional[Callable[[], Awaitable[int]]] = None,
) -> List[Box]:
    """Boxes in reading order with their translation; a box whose translation failed keeps empty text.

    Crops are sent CROP_CONCURRENCY at a time; with `concurrency_probe` the first crop goes alone (it loads the
    model) and the rest use the number the probe reports, one at a time if the probe fails. A box the model rejected (NonTranslationError) or left empty is
    retried with `fallback_crop` after every primary call finished, so a second model is swapped in once per
    page. Raises the first error when the first MAX_CONSECUTIVE_FAILURES crops all fail with a provider error and
    nothing was translated (provider down); a model that merely rejects crops is not "down".
    """
    detected = await asyncio.to_thread(detector, image_bytes)
    if not detected:
        return []
    image = open_rgb(image_bytes)
    crops = [_crop_data_url(image, box) for box in detected]

    async def run(crop: str, gate: asyncio.Semaphore):
        async with gate:
            try:
                return (await translate_crop(crop)).strip(), None
            except Exception as error:
                return "", error

    if concurrency_probe is None:
        gate = asyncio.Semaphore(CROP_CONCURRENCY)
        outcomes = list(await asyncio.gather(*(run(crop, gate) for crop in crops)))
    else:
        outcomes = [await run(crops[0], asyncio.Semaphore(1))]
        try:
            limit = resolve_concurrency(await concurrency_probe())
        except Exception:
            limit = 1
        gate = asyncio.Semaphore(limit)
        outcomes += await asyncio.gather(*(run(crop, gate) for crop in crops[1:]))

    texts: List[str] = []
    for text, error in outcomes:
        texts.append("" if error is not None or len(text) > MAX_BOX_TEXT_CHARS else text)
    head = outcomes[:MAX_CONSECUTIVE_FAILURES]
    if (
        len(head) == MAX_CONSECUTIVE_FAILURES
        and all(error is not None and not isinstance(error, NonTranslationError) for _, error in head)
        and not any(texts)
    ):
        raise head[0][1]

    if fallback_crop is not None:
        for index, (text, error) in enumerate(outcomes):
            if texts[index] or not (isinstance(error, NonTranslationError) or (error is None and not text)):
                continue
            try:
                recovered = (await fallback_crop(crops[index])).strip()
            except Exception:
                continue
            if len(recovered) <= MAX_BOX_TEXT_CHARS:
                texts[index] = recovered

    return [Box(box.x0, box.y0, box.x1, box.y1, text) for box, text in zip(detected, texts)]
