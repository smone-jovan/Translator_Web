import base64
import io

import pymupdf
import pytest

from services.ai.index_translate import validate_image_data_url
from services.pdf_pages import (
    MAX_PDF_PAGES,
    PdfRejectedError,
    PdfTooLargeError,
    classify_page,
    open_pdf,
    page_text,
    render_page_png_data_url,
)

SCAN_TEXT = "这是一页扫描"


def _make_pdf(pages, encrypt=False):
    """pages: list of str (text layer) or None (image-only page)."""
    doc = pymupdf.open()
    for content in pages:
        page = doc.new_page(width=595, height=842)
        if content is None:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
            pix.set_rect(pix.irect, (200, 30, 30))
            page.insert_image(pymupdf.Rect(50, 50, 300, 300), pixmap=pix)
        else:
            page.insert_text((72, 72), content, fontname="china-s")
    kwargs = {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "user_pw": "x", "owner_pw": "y"} if encrypt else {}
    return doc.tobytes(**kwargs)


class TestOpenPdf:
    def test_opens_valid_pdf_and_counts_pages(self):
        doc = open_pdf(_make_pdf(["第一页", "第二页"]))
        assert len(doc) == 2

    def test_rejects_non_pdf_bytes(self):
        with pytest.raises(PdfRejectedError):
            open_pdf(b"<html>not a pdf</html>")

    def test_rejects_corrupt_pdf(self):
        with pytest.raises(PdfRejectedError):
            open_pdf(b"%PDF-1.7\n garbage garbage")

    def test_rejects_encrypted_pdf(self):
        with pytest.raises(PdfRejectedError):
            open_pdf(_make_pdf(["secret"], encrypt=True))

    def test_rejects_too_many_pages(self):
        with pytest.raises(PdfTooLargeError):
            open_pdf(_make_pdf(["p"] * (MAX_PDF_PAGES + 1)))

    def test_rejects_oversized_payload_before_parsing(self):
        with pytest.raises(PdfTooLargeError):
            open_pdf(b"%PDF-" + b"0" * (20 * 1024 * 1024))


class TestClassifyPage:
    def test_long_text_layer_is_text(self):
        doc = open_pdf(_make_pdf(["这是一段足够长的中文文本，用来判断页面带有文字层。"]))
        text = page_text(doc[0])
        assert classify_page(text) == "text"

    def test_image_only_page_is_image(self):
        doc = open_pdf(_make_pdf([None]))
        assert classify_page(page_text(doc[0])) == "image"

    @pytest.mark.parametrize("text", ["", "   \n\t ", "1 2 3"])
    def test_too_little_text_is_image(self, text):
        assert classify_page(text) == "image"


class TestRenderPage:
    def test_render_is_valid_data_url_within_official_edge_range(self):
        doc = open_pdf(_make_pdf([None]))
        url = render_page_png_data_url(doc[0])

        assert validate_image_data_url(url) == url
        from PIL import Image

        img = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        assert 512 <= max(img.size) <= 2048

    def test_huge_page_is_downscaled_to_max_edge(self):
        doc = pymupdf.open()
        doc.new_page(width=5000, height=7000)
        url = render_page_png_data_url(open_pdf(doc.tobytes())[0])

        from PIL import Image

        img = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        assert max(img.size) <= 2048

    def test_tiny_page_is_upscaled_to_min_edge(self):
        doc = pymupdf.open()
        doc.new_page(width=100, height=100)
        url = render_page_png_data_url(open_pdf(doc.tobytes())[0])

        from PIL import Image

        img = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        assert max(img.size) >= 512
