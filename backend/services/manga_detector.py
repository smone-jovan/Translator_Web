"""
Find speech-bubble text and free text on a manga/comic page with the ogkalu/comic-text-and-bubble-detector
ONNX model (RT-DETR-v2, Apache-2.0), on CPU so LM Studio keeps the GPU memory.

The exported model already post-processes its output: it takes `images` (1x3x640x640, RGB, 0..1, no
mean/std) and `orig_target_sizes` ([[width, height]]) and returns `labels`, `boxes` (xyxy in original
pixels) and `scores`. Weights are a local file the user downloads (backend/models/, see ADR-132);
nothing is fetched at runtime.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Sequence

import numpy as np
from PIL import Image

from services.manga_overlay import open_rgb

BUBBLE = 0
TEXT_BUBBLE = 1
TEXT_FREE = 2
_TEXT_LABELS = (TEXT_BUBBLE, TEXT_FREE)

INPUT_SIZE = 640
SCORE_THRESHOLD = 0.4
MAX_BOXES = 25
MIN_BOX_SIDE = 8
DUPLICATE_IOU = 0.5
TALL_RATIO = 2.0
TILE_ASPECT = 1.5
TILE_OVERLAP_RATIO = 0.15
MAX_TILES = 30
MODEL_ENV = "MANGA_DETECTOR_MODEL"
DEFAULT_MODEL = Path(__file__).resolve().parent.parent / "models" / "detector-v4-s_int8.onnx"


class DetectorUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class DetectedBox:
    x0: int
    y0: int
    x1: int
    y1: int
    label: int
    score: float


@lru_cache(maxsize=1)
def load_detector() -> Any:
    path = Path(os.environ.get(MODEL_ENV) or DEFAULT_MODEL)
    if not path.is_file():
        raise DetectorUnavailableError("Text detector model is not installed")
    import onnxruntime as ort  # imported lazily: only needed when overlay is requested

    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def preprocess(image: Image.Image) -> np.ndarray:
    resized = image.convert("RGB").resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
    return (np.asarray(resized, dtype=np.float32) / 255.0).transpose(2, 0, 1)[None]


def _iou(a: DetectedBox, b: DetectedBox) -> float:
    inter_w = min(a.x1, b.x1) - max(a.x0, b.x0)
    inter_h = min(a.y1, b.y1) - max(a.y0, b.y0)
    if inter_w <= 0 or inter_h <= 0:
        return 0.0
    inter = inter_w * inter_h
    union = (a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter
    return inter / union


def select_boxes(
    labels: Sequence[int],
    boxes: Sequence[Sequence[float]],
    scores: Sequence[float],
    width: int,
    height: int,
    *,
    score_threshold: float = SCORE_THRESHOLD,
    max_boxes: int = MAX_BOXES,
) -> List[DetectedBox]:
    """Text boxes only, clamped into the image, de-duplicated, best scores first."""
    candidates: List[DetectedBox] = []
    for label, (x0, y0, x1, y1), score in zip(labels, boxes, scores):
        if int(label) not in _TEXT_LABELS or float(score) < score_threshold:
            continue
        box = DetectedBox(
            max(0, round(x0)), max(0, round(y0)), min(width, round(x1)), min(height, round(y1)), int(label), float(score)
        )
        if box.x1 - box.x0 >= MIN_BOX_SIDE and box.y1 - box.y0 >= MIN_BOX_SIDE:
            candidates.append(box)

    kept: List[DetectedBox] = []
    for box in sorted(candidates, key=lambda b: b.score, reverse=True):
        if all(_iou(box, other) <= DUPLICATE_IOU for other in kept):
            kept.append(box)
        if len(kept) >= max_boxes:
            break
    return kept


def reading_order(boxes: Sequence[DetectedBox], rtl: bool = True) -> List[DetectedBox]:
    """Rows top to bottom; inside a row right to left (manga) or left to right."""
    rows: List[List[DetectedBox]] = []
    for box in sorted(boxes, key=lambda b: (b.y0, b.x0)):
        if rows and (box.y0 + box.y1) / 2 <= rows[-1][0].y1:
            rows[-1].append(box)
        else:
            rows.append([box])
    ordered: List[DetectedBox] = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda b: -b.x0 if rtl else b.x0))
    return ordered


def _tile_spans(width: int, height: int) -> List[tuple]:
    if height <= width * TALL_RATIO:
        return [(0, height)]
    tile_height = int(width * TILE_ASPECT)
    step = tile_height - int(tile_height * TILE_OVERLAP_RATIO)
    spans, top = [], 0
    while True:
        bottom = min(top + tile_height, height)
        spans.append((top, bottom))
        if bottom >= height:
            return spans
        if len(spans) >= MAX_TILES:
            raise ValueError("Image is too tall")
        top += step


def _run_tile(session: Any, image: Image.Image, top: int, bottom: int):
    tile = image.crop((0, top, image.width, bottom))
    labels, boxes, scores = session.run(
        None,
        {
            "images": preprocess(tile),
            "orig_target_sizes": np.array([[tile.width, tile.height]], dtype=np.int64),
        },
    )
    shifted = [[x0, y0 + top, x1, y1 + top] for x0, y0, x1, y1 in boxes[0]]
    return list(labels[0]), shifted, list(scores[0])


def detect_text_boxes(
    image_bytes: bytes, *, session: Optional[Any] = None, rtl: bool = True, max_boxes: int = MAX_BOXES
) -> List[DetectedBox]:
    """Text boxes of one page in reading order. Raises ValueError for unreadable/huge images."""
    image = open_rgb(image_bytes)
    spans = _tile_spans(image.width, image.height)
    session = session or load_detector()

    labels: List[int] = []
    boxes: List[List[float]] = []
    scores: List[float] = []
    for top, bottom in spans:
        tile_labels, tile_boxes, tile_scores = _run_tile(session, image, top, bottom)
        labels += tile_labels
        boxes += tile_boxes
        scores += tile_scores
    return reading_order(select_boxes(labels, boxes, scores, image.width, image.height, max_boxes=max_boxes), rtl)
