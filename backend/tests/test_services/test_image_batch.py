import base64
import io

import pymupdf
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
