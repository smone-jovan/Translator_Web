"""
Image folders for Index-Translate: prepare each uploaded image for the vision model and build the
combined output PDF. Pure functions over bytes: no network, no disk, no database.

Only PNG and JPEG are accepted (what manga scans ship as). Images are decoded by MuPDF and
downscaled to the official 2048 px longest edge before they are sent to the model.
"""
import base64
from typing import List, Sequence

import pymupdf

from services.ai.index_translate import MAX_IMAGE_BYTES, ImageTooLargeError, validate_image_data_url

__all__ = ["ImageRejectedError", "ImageTooLargeError", "build_translated_pdf", "prepare_image_data_url"]

MAX_EDGE_PX = 2048
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"

_PAGE_WIDTH = 595.0
_PAGE_HEIGHT = 842.0
_MAX_IMAGE_PAGE_HEIGHT = 14000.0  # PDF viewers choke above ~14400 pt
_MARGIN = 50.0
_FONT_SIZE = 11.0
_LINE_HEIGHT = 15.0
_LATIN_FONT = "helv"
_CJK_FONT = "china-s"
_LATIN_LIMIT = 0x2FF  # above this the base-14 Latin font cannot draw the character


class ImageRejectedError(ValueError):
    pass


def _mime_for(data: bytes) -> str:
    if data.startswith(_PNG_MAGIC):
        return "png"
    if data.startswith(_JPEG_MAGIC):
        return "jpeg"
    raise ImageRejectedError("Image must be a PNG or JPEG file")


def prepare_image_data_url(data: bytes) -> str:
    """Validate one uploaded image and return a base64 data URL no larger than the model should see."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError(f"Image is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB)")
    mime = _mime_for(data)
    try:
        pixmap = pymupdf.Pixmap(data)
    except Exception:
        raise ImageRejectedError("Image could not be read") from None

    payload = data
    longest = max(pixmap.width, pixmap.height)
    if longest > MAX_EDGE_PX:
        scale = MAX_EDGE_PX / longest
        if pixmap.colorspace is not None and pixmap.colorspace.n == 4:  # CMYK JPEG
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
        resized = pymupdf.Pixmap(pixmap, max(1, round(pixmap.width * scale)), max(1, round(pixmap.height * scale)))
        payload = resized.tobytes(mime)
    return validate_image_data_url(f"data:image/{mime};base64,{base64.b64encode(payload).decode('ascii')}")


def _font_for(text: str) -> str:
    return _CJK_FONT if any(ord(ch) > _LATIN_LIMIT for ch in text) else _LATIN_FONT


def _wrap(paragraph: str, fontname: str, max_width: float) -> List[str]:
    lines: List[str] = []
    current = ""
    for ch in paragraph:
        trial = current + ch
        if pymupdf.get_text_length(trial, fontname=fontname, fontsize=_FONT_SIZE) <= max_width:
            current = trial
            continue
        cut = current.rfind(" ")
        if cut > 0 and ch != " ":
            lines.append(current[:cut])
            current = current[cut + 1:] + ch
        else:
            lines.append(current)
            current = ch.lstrip()
    lines.append(current)
    return lines


def _add_image_page(doc: pymupdf.Document, image: bytes) -> None:
    pixmap = pymupdf.Pixmap(image)
    height = min(_PAGE_WIDTH * pixmap.height / pixmap.width, _MAX_IMAGE_PAGE_HEIGHT)
    page = doc.new_page(width=_PAGE_WIDTH, height=height)
    page.insert_image(page.rect, stream=image)


def _add_text_pages(doc: pymupdf.Document, heading: str, text: str) -> None:
    max_width = _PAGE_WIDTH - 2 * _MARGIN
    page = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
    y = _MARGIN
    page.insert_text((_MARGIN, y), heading, fontname=_LATIN_FONT, fontsize=_FONT_SIZE - 2)
    y += 2 * _LINE_HEIGHT
    for paragraph in text.splitlines() or [""]:
        for line in _wrap(paragraph, _font_for(paragraph), max_width):
            if y > _PAGE_HEIGHT - _MARGIN:
                page = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
                y = _MARGIN
            if line:
                page.insert_text((_MARGIN, y), line, fontname=_font_for(line), fontsize=_FONT_SIZE)
            y += _LINE_HEIGHT


def build_translated_pdf(images: Sequence[bytes], translations: Sequence[str]) -> bytes:
    """One image page followed by its translation page(s), for every image in order."""
    if len(images) != len(translations):
        raise ValueError("Every image needs exactly one translation")
    doc = pymupdf.open()
    try:
        for number, (image, translation) in enumerate(zip(images, translations), start=1):
            _add_image_page(doc, image)
            _add_text_pages(doc, f"Terjemahan halaman {number}", translation)
        return doc.tobytes()
    finally:
        doc.close()
