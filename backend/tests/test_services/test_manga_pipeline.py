import base64
import io

import pytest
from PIL import Image

from services.manga_detector import DetectedBox, TEXT_BUBBLE
from services.manga_overlay import Box
from services.manga_pipeline import MAX_CONSECUTIVE_FAILURES, translate_page_boxes


def _png(width=600, height=900) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _detected(*rects):
    return lambda _bytes: [DetectedBox(x0, y0, x1, y1, TEXT_BUBBLE, 0.9) for x0, y0, x1, y1 in rects]


def _decode(data_url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1])))


@pytest.mark.asyncio
async def test_translates_each_box_in_order_and_returns_boxes_with_text():
    seen = []

    async def translate(data_url):
        seen.append(data_url)
        return f"teks-{len(seen)}"

    boxes = await translate_page_boxes(_png(), translate, detector=_detected((300, 20, 400, 100), (20, 20, 120, 100)))

    assert boxes == [Box(300, 20, 400, 100, "teks-1"), Box(20, 20, 120, 100, "teks-2")]
    assert all(url.startswith("data:image/png;base64,") for url in seen)


@pytest.mark.asyncio
async def test_crop_includes_a_margin_and_is_upscaled_to_the_vision_minimum():
    crops = []

    async def translate(data_url):
        crops.append(_decode(data_url))
        return "x"

    await translate_page_boxes(_png(), translate, detector=_detected((100, 100, 150, 130)))

    (crop,) = crops
    assert max(crop.size) >= 512
    assert crop.width / crop.height == pytest.approx((50 + 12) / (30 + 12), rel=0.05)


@pytest.mark.asyncio
async def test_margin_is_clamped_at_the_image_edge():
    crops = []

    async def translate(data_url):
        crops.append(_decode(data_url))
        return "x"

    await translate_page_boxes(_png(200, 200), translate, detector=_detected((0, 0, 40, 40)))

    assert crops[0].width / crops[0].height == pytest.approx(46 / 46, rel=0.05)


@pytest.mark.asyncio
async def test_one_failing_box_is_left_without_text_and_others_continue():
    calls = []

    async def translate(_url):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return "ok"

    boxes = await translate_page_boxes(
        _png(), translate, detector=_detected((10, 10, 60, 60), (100, 10, 160, 60), (200, 10, 260, 60))
    )

    assert [b.text for b in boxes] == ["ok", "", "ok"]


@pytest.mark.asyncio
async def test_gives_up_after_consecutive_failures_with_nothing_translated():
    async def translate(_url):
        raise RuntimeError("connection refused")

    rects = [(i * 70, 10, i * 70 + 50, 60) for i in range(MAX_CONSECUTIVE_FAILURES + 3)]

    with pytest.raises(RuntimeError):
        await translate_page_boxes(_png(900, 200), translate, detector=_detected(*rects))


@pytest.mark.asyncio
async def test_no_boxes_returns_empty_without_calling_the_model():
    async def translate(_url):
        raise AssertionError("must not be called")

    assert await translate_page_boxes(_png(), translate, detector=_detected()) == []


@pytest.mark.asyncio
async def test_blank_translation_means_no_text_for_that_box():
    async def translate(_url):
        return "   "

    boxes = await translate_page_boxes(_png(), translate, detector=_detected((10, 10, 80, 80)))

    assert boxes == [Box(10, 10, 80, 80, "")]
