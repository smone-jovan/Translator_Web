"""
One manga page -> translated text boxes: detect text boxes, crop each (with a small margin), and ask the
vision model to translate the crop. The model call is injected so this module stays free of providers,
routers and the database.
"""
import asyncio
import base64
import io
from typing import Awaitable, Callable, List

from PIL import Image

from services.ai.index_translate import validate_image_data_url
from services.manga_detector import detect_text_boxes
from services.manga_overlay import Box, open_rgb

CROP_MARGIN_PX = 6
MIN_CROP_EDGE_PX = 512
MAX_CROP_EDGE_PX = 2048
MAX_CONSECUTIVE_FAILURES = 3

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
    image_bytes: bytes, translate_crop: TranslateCrop, *, detector=detect_text_boxes
) -> List[Box]:
    """Boxes in reading order with their translation; a box whose translation failed keeps empty text.

    Raises the last error when the first MAX_CONSECUTIVE_FAILURES crops all fail (provider down).
    """
    detected = await asyncio.to_thread(detector, image_bytes)
    if not detected:
        return []
    image = open_rgb(image_bytes)

    result: List[Box] = []
    consecutive_failures = 0
    any_success = False
    for box in detected:
        try:
            text = (await translate_crop(_crop_data_url(image, box))).strip()
        except Exception:
            consecutive_failures += 1
            if not any_success and consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                raise
            text = ""
        else:
            consecutive_failures = 0
            any_success = any_success or bool(text)
        result.append(Box(box.x0, box.y0, box.x1, box.y1, text))
    return result
