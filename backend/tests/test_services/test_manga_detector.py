import io
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from services.manga_detector import (
    DetectedBox,
    DetectorUnavailableError,
    TEXT_BUBBLE,
    TEXT_FREE,
    TILE_ASPECT,
    TILE_OVERLAP_RATIO,
    BUBBLE,
    detect_text_boxes,
    load_detector,
    preprocess,
    reading_order,
    select_boxes,
)


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeSession:
    """Mimics the onnx model: inputs images + orig_target_sizes([w, h]); outputs labels, boxes(xyxy px), scores."""

    def __init__(self, per_call):
        self.per_call = list(per_call)  # list of (labels, boxes, scores) lists, one per call
        self.feeds = []

    def run(self, _outputs, feed):
        self.feeds.append(feed)
        labels, boxes, scores = self.per_call[len(self.feeds) - 1] if self.per_call else ([], [], [])
        return [
            np.array([labels], dtype=np.int64).reshape(1, -1),
            np.array([boxes], dtype=np.float32).reshape(1, -1, 4),
            np.array([scores], dtype=np.float32).reshape(1, -1),
        ]


class TestPreprocess:
    def test_returns_640_chw_float32_in_unit_range(self):
        array = preprocess(Image.new("RGB", (300, 500), (255, 255, 255)))

        assert array.shape == (1, 3, 640, 640)
        assert array.dtype == np.float32
        assert np.allclose(array, 1.0)

    def test_keeps_channel_order_rgb(self):
        array = preprocess(Image.new("RGB", (64, 64), (255, 0, 0)))

        assert np.allclose(array[0, 0], 1.0) and np.allclose(array[0, 1:], 0.0)


class TestSelectBoxes:
    def test_keeps_only_text_classes_above_threshold(self):
        labels = [BUBBLE, TEXT_BUBBLE, TEXT_FREE, TEXT_BUBBLE]
        boxes = [[0, 0, 100, 100], [10, 10, 60, 40], [200, 200, 260, 240], [300, 300, 340, 330]]
        scores = [0.99, 0.9, 0.8, 0.2]

        kept = select_boxes(labels, boxes, scores, 400, 400)

        assert [b.label for b in kept] == [TEXT_BUBBLE, TEXT_FREE]  # highest score first
        assert [b.score for b in kept] == pytest.approx([0.9, 0.8])

    def test_clamps_boxes_into_the_image_and_drops_tiny_ones(self):
        kept = select_boxes(
            [TEXT_BUBBLE, TEXT_BUBBLE], [[-20, -20, 50, 50], [10, 10, 14, 14]], [0.9, 0.9], 100, 100
        )

        assert [(b.x0, b.y0, b.x1, b.y1) for b in kept] == [(0, 0, 50, 50)]

    def test_duplicate_overlapping_boxes_keep_the_higher_score(self):
        kept = select_boxes(
            [TEXT_BUBBLE, TEXT_FREE], [[10, 10, 110, 60], [12, 11, 112, 61]], [0.7, 0.95], 300, 300
        )

        assert len(kept) == 1 and kept[0].score == pytest.approx(0.95)

    def test_limits_the_number_of_boxes_keeping_highest_scores(self):
        boxes = [[i * 30, 0, i * 30 + 20, 20] for i in range(10)]
        scores = [0.5 + i * 0.04 for i in range(10)]

        kept = select_boxes([TEXT_BUBBLE] * 10, boxes, scores, 400, 100, max_boxes=3)

        assert len(kept) == 3
        assert min(b.score for b in kept) >= 0.5 + 7 * 0.04 - 1e-6


class TestReadingOrder:
    def _box(self, x0, y0, x1=None, y1=None):
        return DetectedBox(x0, y0, x1 or x0 + 40, y1 or y0 + 40, TEXT_BUBBLE, 0.9)

    def test_manga_order_is_top_to_bottom_right_to_left(self):
        top_right, top_left = self._box(300, 10), self._box(20, 20)
        bottom = self._box(150, 200)

        ordered = reading_order([bottom, top_left, top_right], rtl=True)

        assert ordered == [top_right, top_left, bottom]

    def test_left_to_right_order(self):
        top_right, top_left = self._box(300, 10), self._box(20, 20)

        assert reading_order([top_right, top_left], rtl=False) == [top_left, top_right]


class TestDetectTextBoxes:
    def test_runs_model_with_width_height_order_and_returns_pixel_boxes(self):
        session = FakeSession([([TEXT_BUBBLE], [[10, 20, 110, 80]], [0.9])])
        image = Image.new("RGB", (400, 500), (255, 255, 255))

        boxes = detect_text_boxes(_png(image), session=session)

        (feed,) = session.feeds
        assert feed["orig_target_sizes"].tolist() == [[400, 500]]
        assert feed["images"].shape == (1, 3, 640, 640)
        assert [(b.x0, b.y0, b.x1, b.y1) for b in boxes] == [(10, 20, 110, 80)]

    def test_tall_webtoon_is_tiled_and_boxes_are_offset_back(self):
        image = Image.new("RGB", (400, 3000), (255, 255, 255))
        session = FakeSession([([], [], []), ([TEXT_FREE], [[50, 100, 150, 160]], [0.9])] + [([], [], [])] * 10)

        boxes = detect_text_boxes(_png(image), session=session)

        assert len(session.feeds) > 1
        second_tile_height = session.feeds[1]["orig_target_sizes"].tolist()[0][1]
        assert second_tile_height <= 1000
        assert len(boxes) == 1
        assert boxes[0].y0 > 100  # shifted by the tile offset

    def test_box_seen_in_two_overlapping_tiles_is_reported_once(self):
        width = 400
        tile_height = int(width * TILE_ASPECT)
        step = tile_height - int(tile_height * TILE_OVERLAP_RATIO)
        absolute_top, absolute_bottom = step + 20, step + 70  # inside both tile 0 and tile 1
        in_tile_0 = ([TEXT_FREE], [[50, absolute_top, 150, absolute_bottom]], [0.9])
        in_tile_1 = ([TEXT_FREE], [[52, absolute_top - step, 151, absolute_bottom - step]], [0.85])
        session = FakeSession([in_tile_0, in_tile_1] + [([], [], [])] * 20)

        boxes = detect_text_boxes(_png(Image.new("RGB", (width, 3000), (255, 255, 255))), session=session)

        assert len(boxes) == 1
        assert boxes[0].score == pytest.approx(0.9)

    def test_rejects_non_images_and_huge_images(self):
        with pytest.raises(ValueError):
            detect_text_boxes(b"nope", session=FakeSession([]))
        with pytest.raises(ValueError):
            detect_text_boxes(_png(Image.new("L", (9000, 9000))), session=FakeSession([]))

    def test_returns_reading_order(self):
        session = FakeSession(
            [([TEXT_BUBBLE, TEXT_BUBBLE], [[20, 20, 80, 60], [300, 20, 360, 60]], [0.9, 0.9])]
        )

        boxes = detect_text_boxes(_png(Image.new("RGB", (400, 500))), session=session, rtl=True)

        assert [b.x0 for b in boxes] == [300, 20]


class TestLoadDetector:
    def test_missing_model_file_raises_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MANGA_DETECTOR_MODEL", str(tmp_path / "missing.onnx"))
        load_detector.cache_clear()

        with pytest.raises(DetectorUnavailableError):
            load_detector()

        load_detector.cache_clear()


MODEL = Path(os.environ.get("MANGA_DETECTOR_MODEL", Path(__file__).resolve().parents[2] / "models" / "detector-v4-s_int8.onnx"))


@pytest.mark.skipif(not MODEL.exists(), reason="detector model not downloaded (see ADR-132)")
def test_real_model_finds_a_speech_bubble_on_a_synthetic_page():
    load_detector.cache_clear()
    image = Image.new("RGB", (500, 800), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.ellipse((260, 50, 470, 200), fill=(255, 255, 255), outline=(0, 0, 0), width=3)
    for i in range(3):
        draw.rectangle((300, 85 + i * 22, 430, 97 + i * 22), fill=(20, 20, 20))

    boxes = detect_text_boxes(_png(image))

    assert any(250 <= (b.x0 + b.x1) / 2 <= 480 and 40 <= (b.y0 + b.y1) / 2 <= 210 for b in boxes)
