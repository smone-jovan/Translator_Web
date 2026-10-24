import io

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from services.manga_overlay import Box, erase_boxes, fit_text, render_overlay


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _page(size=(400, 600), color=(255, 255, 255)) -> Image.Image:
    return Image.new("RGB", size, color)


class TestEraseBoxes:
    def test_box_area_becomes_uniform_background_color(self):
        image = _page(color=(250, 240, 230))
        ImageDraw.Draw(image).text((60, 60), "ABCDEF", fill=(0, 0, 0))

        erased = erase_boxes(image, [Box(50, 50, 200, 120, "")])

        area = np.asarray(erased.crop((50, 50, 200, 120)))
        assert (area == (250, 240, 230)).all()

    def test_pixels_outside_boxes_are_untouched(self):
        image = _page()
        ImageDraw.Draw(image).rectangle((300, 300, 380, 380), fill=(10, 20, 30))

        erased = erase_boxes(image, [Box(10, 10, 100, 100, "")])

        assert np.array_equal(
            np.asarray(erased.crop((300, 300, 380, 380))), np.asarray(image.crop((300, 300, 380, 380)))
        )

    def test_does_not_mutate_the_input_image(self):
        image = _page()
        ImageDraw.Draw(image).text((20, 20), "KEEP", fill=(0, 0, 0))
        before = np.asarray(image).copy()

        erase_boxes(image, [Box(0, 0, 100, 100, "")])

        assert np.array_equal(np.asarray(image), before)

    def test_background_color_comes_from_box_edge_not_from_the_text(self):
        image = _page(color=(200, 220, 240))
        ImageDraw.Draw(image).rectangle((70, 70, 130, 100), fill=(0, 0, 0))  # dark text blob in the middle

        erased = erase_boxes(image, [Box(50, 50, 150, 120, "")])

        assert tuple(np.asarray(erased)[85, 100]) == (200, 220, 240)


class TestFitText:
    def _font(self, size: int):
        return ImageFont.load_default(size)

    def test_lines_fit_inside_the_box(self):
        font_size, lines = fit_text("Ini adalah kalimat terjemahan yang cukup panjang untuk dibungkus", 160, 120)

        font = self._font(font_size)
        assert all(font.getlength(line) <= 160 for line in lines)
        assert len(lines) * font_size * 1.2 <= 120 + font_size

    def test_longer_text_gets_a_smaller_or_equal_font(self):
        short_size, _ = fit_text("Halo", 160, 120)
        long_size, _ = fit_text("Halo " * 40, 160, 120)

        assert long_size <= short_size

    def test_font_size_stays_within_bounds(self):
        size, _ = fit_text("Halo", 2000, 2000)

        assert 8 <= size <= 40

    def test_overflowing_text_is_truncated_with_ellipsis_at_min_size(self):
        size, lines = fit_text("kata " * 500, 80, 40)

        assert size == 8
        assert lines[-1].endswith("…")

    def test_empty_text_gives_no_lines(self):
        assert fit_text("   ", 100, 100)[1] == []

    def test_explicit_newlines_are_kept_as_breaks(self):
        _, lines = fit_text("satu\ndua", 400, 200)

        assert lines == ["satu", "dua"]


class TestRenderOverlay:
    def test_returns_png_with_same_size_and_changed_box_area(self):
        original = _page(color=(255, 255, 255))
        ImageDraw.Draw(original).text((60, 60), "原文", fill=(0, 0, 0))
        box = Box(40, 40, 240, 160, "Halo dunia")

        result = Image.open(io.BytesIO(render_overlay(_png(original), [box])))

        assert result.format == "PNG"
        assert result.size == original.size
        after = np.asarray(result.convert("RGB").crop((40, 40, 240, 160)))
        before = np.asarray(original.crop((40, 40, 240, 160)))
        assert not np.array_equal(after, before)
        assert (after < 128).any()  # dark text pixels were drawn

    def test_no_boxes_returns_equivalent_image(self):
        original = _page()

        result = Image.open(io.BytesIO(render_overlay(_png(original), [])))

        assert np.array_equal(np.asarray(result.convert("RGB")), np.asarray(original))

    def test_boxes_outside_or_degenerate_are_ignored_safely(self):
        original = _page()
        boxes = [Box(-50, -50, 20, 20, "ok"), Box(500, 500, 900, 900, "outside"), Box(10, 10, 10, 50, "flat")]

        result = Image.open(io.BytesIO(render_overlay(_png(original), boxes)))

        assert result.size == original.size

    def test_rejects_non_image_bytes(self):
        with pytest.raises(ValueError):
            render_overlay(b"not an image", [Box(0, 0, 10, 10, "x")])

    def test_rejects_decompression_bombs(self):
        huge = Image.new("L", (9000, 9000))  # 81 MP, above the pixel cap

        with pytest.raises(ValueError):
            render_overlay(_png(huge), [])
