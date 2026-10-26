import base64
import io

import pytest
from PIL import Image

from services.manga_detector import DetectedBox, TEXT_BUBBLE
from services.manga_overlay import Box
from services.manga_pipeline import (
    CROP_MARGIN_PX,
    MAX_BOX_TEXT_CHARS,
    MAX_CONSECUTIVE_FAILURES,
    MIN_CROP_EDGE_PX,
    translate_page_boxes,
)


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
    assert max(crop.size) >= MIN_CROP_EDGE_PX
    assert crop.width / crop.height == pytest.approx((50 + 2 * CROP_MARGIN_PX) / (30 + 2 * CROP_MARGIN_PX), rel=0.05)


def test_crop_settings_follow_the_measured_best_values():
    # Measured on a real chapter (ADR-136): upscaling tiny crops to 512 px made the 2B model loop.
    assert (MIN_CROP_EDGE_PX, CROP_MARGIN_PX) == (256, 12)


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


@pytest.mark.asyncio
async def test_runaway_text_longer_than_the_box_limit_is_dropped_so_export_still_works():
    async def translate(_url):
        return "x" * (MAX_BOX_TEXT_CHARS + 1)

    boxes = await translate_page_boxes(_png(), translate, detector=_detected((20, 20, 120, 100)))

    assert boxes == [Box(20, 20, 120, 100, "")]


# ---- fallback for boxes the primary model could not translate (ADR-137) ---------------------------------

import asyncio  # noqa: E402

from services.manga_pipeline import CROP_CONCURRENCY  # noqa: E402
from services.translation_guard import NonTranslationError  # noqa: E402

THREE = ((10, 10, 60, 60), (100, 10, 160, 60), (200, 10, 260, 60))


@pytest.mark.asyncio
async def test_fallback_translates_boxes_the_primary_model_rejected_or_left_empty():
    async def primary(_url):
        primary.n += 1
        if primary.n == 1:
            raise NonTranslationError("loop")
        if primary.n == 2:
            return ""
        return "ok"

    primary.n = 0
    fallback_calls = []

    async def fallback(url):
        fallback_calls.append(url)
        return "dari-cadangan"

    boxes = await translate_page_boxes(_png(), primary, detector=_detected(*THREE), fallback_crop=fallback)

    assert [b.text for b in boxes] == ["dari-cadangan", "dari-cadangan", "ok"]
    assert len(fallback_calls) == 2


@pytest.mark.asyncio
async def test_fallback_is_not_used_for_provider_errors_or_when_not_configured():
    async def primary(_url):
        raise RuntimeError("connection refused")

    async def fallback(_url):
        raise AssertionError("must not be called")

    with pytest.raises(RuntimeError):
        await translate_page_boxes(_png(), primary, detector=_detected(*THREE), fallback_crop=fallback)

    async def rejecting(_url):
        raise NonTranslationError("description")

    boxes = await translate_page_boxes(_png(), rejecting, detector=_detected(*THREE))
    assert [b.text for b in boxes] == ["", "", ""]


@pytest.mark.asyncio
async def test_failing_fallback_leaves_the_box_empty_and_keeps_going():
    async def primary(_url):
        raise NonTranslationError("loop")

    async def fallback(_url):
        raise RuntimeError("second model is down")

    boxes = await translate_page_boxes(_png(), primary, detector=_detected(*THREE), fallback_crop=fallback)

    assert [b.text for b in boxes] == ["", "", ""]


@pytest.mark.asyncio
async def test_fallback_runs_after_every_primary_call_so_the_model_is_swapped_once():
    order = []

    async def primary(_url):
        order.append("p")
        if len(order) == 1:
            raise NonTranslationError("loop")
        return "ok"

    async def fallback(_url):
        order.append("f")
        return "cadangan"

    await translate_page_boxes(_png(), primary, detector=_detected(*THREE), fallback_crop=fallback)

    assert order == ["p", "p", "p", "f"]


@pytest.mark.asyncio
async def test_crops_are_translated_concurrently_up_to_the_limit_and_order_is_kept():
    in_flight = peak = 0

    async def translate(url):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return f"{_decode(url).width}"

    rects = [(i * 70, 10, i * 70 + 50 + i, 60) for i in range(10)]
    boxes = await translate_page_boxes(_png(900, 200), translate, detector=_detected(*rects))

    assert 1 < peak <= CROP_CONCURRENCY
    assert CROP_CONCURRENCY == 4
    assert [b.x0 for b in boxes] == [r[0] for r in rects]


# ---- concurrency follows the server's parallel slots (probed after the first crop) -------------------------

@pytest.mark.asyncio
async def test_probe_sets_concurrency_after_the_first_crop_and_first_crop_runs_alone():
    in_flight = peak = 0
    peaks_during_first = []

    async def translate(_url):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        if not peaks_during_first:
            peaks_during_first.append(in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return "ok"

    probed = []

    async def probe():
        probed.append(1)
        return 2

    rects = [(i * 70, 10, i * 70 + 50, 60) for i in range(8)]
    boxes = await translate_page_boxes(_png(900, 200), translate, detector=_detected(*rects), concurrency_probe=probe)

    assert len(boxes) == 8 and probed == [1]
    assert peaks_during_first == [1] and peak == 2


@pytest.mark.asyncio
async def test_failing_probe_falls_back_to_one_at_a_time():
    in_flight = peak = 0

    async def translate(_url):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.005)
        in_flight -= 1
        return "ok"

    async def probe():
        raise RuntimeError("no api")

    rects = [(i * 70, 10, i * 70 + 50, 60) for i in range(5)]
    boxes = await translate_page_boxes(_png(900, 200), translate, detector=_detected(*rects), concurrency_probe=probe)

    assert [b.text for b in boxes] == ["ok"] * 5 and peak == 1
