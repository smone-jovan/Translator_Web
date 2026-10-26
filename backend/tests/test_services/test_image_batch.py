import base64
import io

import pymupdf
from PIL import Image
import pytest

from services.ai.index_translate import MAX_IMAGE_BYTES, validate_image_data_url
from services.image_batch import (
    ImageRejectedError,
    ImageTooLargeError,
    build_translated_pdf,
    prepare_image_data_url,
)


def make_image(width, height, fmt="png"):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height))
    pix.clear_with(180)
    return pix.tobytes(fmt)


def decoded_size(data_url):
    pix = pymupdf.Pixmap(base64.b64decode(data_url.split(",", 1)[1]))
    return pix.width, pix.height


class TestPrepareImage:
    @pytest.mark.parametrize("fmt,mime", [("png", "png"), ("jpeg", "jpeg")])
    def test_accepts_png_and_jpeg(self, fmt, mime):
        url = prepare_image_data_url(make_image(800, 1200, fmt))

        assert url.startswith(f"data:image/{mime};base64,")
        assert validate_image_data_url(url) == url

    def test_large_image_is_downscaled_to_max_edge(self):
        url = prepare_image_data_url(make_image(3000, 4500))

        assert max(decoded_size(url)) <= 2048

    def test_small_image_keeps_its_size(self):
        assert decoded_size(prepare_image_data_url(make_image(700, 900))) == (700, 900)

    @pytest.mark.parametrize("payload", [b"", b"<html></html>", b"GIF89a....", b"RIFF\x00\x00\x00\x00WEBPVP8 "])
    def test_rejects_non_png_jpeg(self, payload):
        with pytest.raises(ImageRejectedError):
            prepare_image_data_url(payload)

    def test_rejects_images_with_too_many_pixels_before_decoding(self, monkeypatch):
        monkeypatch.setattr("services.image_batch.MAX_PIXELS", 1000)

        with pytest.raises(ImageRejectedError, match="pixels"):
            prepare_image_data_url(make_image(100, 100))

    def test_rejects_corrupt_image(self):
        with pytest.raises(ImageRejectedError):
            prepare_image_data_url(b"\x89PNG\r\n\x1a\nnot really a png")

    def test_rejects_oversized_payload(self):
        with pytest.raises(ImageTooLargeError):
            prepare_image_data_url(b"\x89PNG\r\n\x1a\n" + b"0" * (MAX_IMAGE_BYTES + 1))


class TestBuildTranslatedPdf:
    def test_each_image_gets_an_image_page_then_a_text_page(self):
        images = [make_image(600, 900, "jpeg"), make_image(600, 900)]
        pdf = build_translated_pdf(images, ["Halo dunia.", "Sampai jumpa."])

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        assert len(doc) == 4
        assert "Halo dunia." in doc[1].get_text()
        assert "Sampai jumpa." in doc[3].get_text()
        assert doc[0].get_text().strip() == ""
        assert doc[0].get_images()

    def test_long_translation_flows_onto_extra_pages(self):
        text = "\n".join(f"Baris nomor {i} dengan beberapa kata tambahan." for i in range(300))
        doc = pymupdf.open(stream=build_translated_pdf([make_image(600, 900)], [text]), filetype="pdf")

        assert len(doc) > 2
        assert "Baris nomor 299" in doc[len(doc) - 1].get_text()

    def test_mismatched_counts_are_rejected(self):
        with pytest.raises(ValueError):
            build_translated_pdf([make_image(100, 100)], [])

    def test_empty_translation_still_produces_a_page(self):
        doc = pymupdf.open(stream=build_translated_pdf([make_image(600, 900)], [""]), filetype="pdf")

        assert len(doc) == 2

    def test_cjk_characters_do_not_break_rendering(self):
        pdf = build_translated_pdf([make_image(600, 900)], ["Selamat 你好 dunia"])

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        assert "你好" in doc[1].get_text()


class TestBuildTranslatedPdfWithOverlays:
    def _darkness_in_box(self, doc, page_number, box):
        page = doc[page_number]
        zoom = 2
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        scale = pix.width / page.rect.width
        sx = pix.width / 600  # source image is 600 px wide and fills the page width
        x0, y0, x1, y1 = (int(v * sx) for v in box)
        samples = pix.samples_mv
        dark = 0
        for y in range(y0, min(y1, pix.height)):
            row = y * pix.stride
            for x in range(x0, min(x1, pix.width)):
                if samples[row + x * pix.n] < 100:
                    dark += 1
        return dark

    def test_overlay_page_replaces_the_original_image_page(self):
        from services.manga_overlay import Box

        box = Box(100, 100, 400, 300, "Halo dunia")
        pdf = build_translated_pdf([make_image(600, 900)], ["Halo dunia"], overlays=[[box]])

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        assert len(doc) == 2
        assert self._darkness_in_box(doc, 0, (100, 100, 400, 300)) > 50

    def test_overlay_pages_are_embedded_as_jpeg_so_the_pdf_stays_small(self):
        from services.manga_overlay import Box

        noisy = Image.effect_noise((1280, 1790), 60).convert("RGB")
        buffer = io.BytesIO()
        noisy.save(buffer, "PNG")
        box = Box(100, 100, 400, 300, "Halo dunia")

        pdf = build_translated_pdf([buffer.getvalue()], ["Halo"], overlays=[[box]], include_text_pages=False)

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        (image_info,) = doc[0].get_images(full=True)
        assert doc.extract_image(image_info[0])["ext"] == "jpeg"
        assert len(pdf) < len(buffer.getvalue()) / 3

    def test_without_overlays_image_page_stays_blank(self):
        pdf = build_translated_pdf([make_image(600, 900)], ["Halo dunia"])

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        assert self._darkness_in_box(doc, 0, (100, 100, 400, 300)) == 0

    def test_text_pages_can_be_left_out(self):
        from services.manga_overlay import Box

        pdf = build_translated_pdf(
            [make_image(600, 900), make_image(600, 900)],
            ["a", "b"],
            overlays=[[Box(100, 100, 400, 300, "a")], []],
            include_text_pages=False,
        )

        assert len(pymupdf.open(stream=pdf, filetype="pdf")) == 2

    def test_overlay_count_must_match_images(self):
        with pytest.raises(ValueError):
            build_translated_pdf([make_image(100, 100)], ["a"], overlays=[[], []])
