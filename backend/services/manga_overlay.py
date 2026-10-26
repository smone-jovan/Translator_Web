"""
Draw translated text over detected text boxes of a manga/comic page. Pure functions over bytes and
Pillow images: no network, no database, no files other than the optional font named by
MANGA_OVERLAY_FONT.

Boxes come from a text detector (or, on export, from the client), so every coordinate is treated as
untrusted: clamped into the image, and degenerate boxes are skipped.
"""
import io
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

MAX_PIXELS = 50_000_000
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 40
LINE_SPACING = 1.2
BOX_PADDING = 4
EDGE_RING = 3
MIN_BOX_SIDE = 2
ELLIPSIS = "…"
FONT_ENV = "MANGA_OVERLAY_FONT"
TEXT_COLOR = (0, 0, 0)
ERASE_OPACITY = 1.0  # solid patch; erase_boxes still supports lower values (0.8 was tried and reverted)


@dataclass(frozen=True)
class Box:
    x0: int
    y0: int
    x1: int
    y1: int
    text: str = ""


@lru_cache(maxsize=64)
def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Pillow's bundled font, or the TrueType file named by MANGA_OVERLAY_FONT when it loads."""
    path = os.environ.get(FONT_ENV)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def _clamp(box: Box, width: int, height: int) -> Optional[Box]:
    x0, y0 = max(0, box.x0), max(0, box.y0)
    x1, y1 = min(width, box.x1), min(height, box.y1)
    if x1 - x0 < MIN_BOX_SIDE or y1 - y0 < MIN_BOX_SIDE:
        return None
    return Box(x0, y0, x1, y1, box.text)


def _background_color(image: Image.Image, box: Box) -> Tuple[int, ...]:
    """Median of the box border ring: the paper color around the text, not the ink inside."""
    region = np.asarray(image.crop((box.x0, box.y0, box.x1, box.y1)))
    ring = max(1, min(EDGE_RING, region.shape[0] // 4, region.shape[1] // 4))
    edges = np.concatenate(
        [
            region[:ring].reshape(-1, region.shape[2]),
            region[-ring:].reshape(-1, region.shape[2]),
            region[:, :ring].reshape(-1, region.shape[2]),
            region[:, -ring:].reshape(-1, region.shape[2]),
        ]
    )
    return tuple(int(v) for v in np.median(edges, axis=0))


def erase_boxes(image: Image.Image, boxes: Sequence[Box], opacity: float = 1.0) -> Image.Image:
    """Cover every box with its surrounding color at the given opacity (1.0 = solid). Returns a new RGB image."""
    result = image.convert("RGB")
    if result is image:
        result = image.copy()
    for raw in boxes:
        box = _clamp(raw, *result.size)
        if box is None:
            continue
        area = (box.x0, box.y0, box.x1, box.y1)
        patch = Image.new("RGB", (box.x1 - box.x0, box.y1 - box.y0), _background_color(result, box))
        result.paste(Image.blend(result.crop(area), patch, opacity), area)
    return result


def _split_long_word(word: str, size: int, max_width: float) -> List[str]:
    font = get_font(size)
    pieces, current = [], ""
    for ch in word:
        if current and font.getlength(current + ch) > max_width:
            pieces.append(current)
            current = ch
        else:
            current += ch
    return pieces + [current]


def _wrap(text: str, size: int, max_width: float) -> List[str]:
    font = get_font(size)
    lines: List[str] = []
    for paragraph in text.splitlines():
        current = ""
        for word in paragraph.split():
            for piece in _split_long_word(word, size, max_width):
                trial = f"{current} {piece}".strip()
                if current and font.getlength(trial) > max_width:
                    lines.append(current)
                    current = piece
                else:
                    current = trial
        lines.append(current)
    return lines


def _line_height(size: int) -> int:
    return round(size * LINE_SPACING)


def _truncate(lines: List[str], size: int, max_width: float, max_lines: int) -> List[str]:
    font = get_font(size)
    kept = lines[:max_lines]
    last = kept[-1].rstrip()
    while last and font.getlength(last + ELLIPSIS) > max_width:
        last = last[:-1].rstrip()
    kept[-1] = last + ELLIPSIS
    return kept


def fit_text(text: str, width: float, height: float) -> Tuple[int, List[str]]:
    """Largest font size (8-40) whose wrapped lines fit the box; truncated with an ellipsis if even 8 does not."""
    if not text.strip():
        return MIN_FONT_SIZE, []
    best: Optional[Tuple[int, List[str]]] = None
    low, high = MIN_FONT_SIZE, MAX_FONT_SIZE
    while low <= high:
        size = (low + high) // 2
        lines = _wrap(text, size, width)
        if len(lines) * _line_height(size) <= height:
            best = (size, lines)
            low = size + 1
        else:
            high = size - 1
    if best is not None:
        return best
    lines = _wrap(text, MIN_FONT_SIZE, width)
    max_lines = max(1, int(height // _line_height(MIN_FONT_SIZE)))
    return MIN_FONT_SIZE, _truncate(lines, MIN_FONT_SIZE, width, max_lines)


def _draw_text(image: Image.Image, box: Box) -> None:
    inner_w = box.x1 - box.x0 - 2 * BOX_PADDING
    inner_h = box.y1 - box.y0 - 2 * BOX_PADDING
    if inner_w < 1 or inner_h < 1:
        return
    size, lines = fit_text(box.text, inner_w, inner_h)
    if not lines:
        return
    font = get_font(size)
    line_h = _line_height(size)
    draw = ImageDraw.Draw(image)
    y = box.y0 + BOX_PADDING + (inner_h - len(lines) * line_h) / 2
    for line in lines:
        x = box.x0 + BOX_PADDING + (inner_w - font.getlength(line)) / 2
        draw.text((x, y), line, font=font, fill=TEXT_COLOR)
        y += line_h


def open_rgb(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("Image has too many pixels")
        return image.convert("RGB")
    except ValueError:
        raise
    except Exception:
        raise ValueError("Image could not be read") from None


def render_overlay(image_bytes: bytes, boxes: Sequence[Box]) -> bytes:
    """Erase the original text in every box that has a translation and draw the translation instead. Returns PNG bytes."""
    image = open_rgb(image_bytes)
    translated = [b for b in boxes if b.text.strip()]
    result = erase_boxes(image, translated, ERASE_OPACITY)
    for raw in translated:
        box = _clamp(raw, *result.size)
        if box is not None:
            _draw_text(result, box)
    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    return buffer.getvalue()
