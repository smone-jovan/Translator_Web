"""
PDF -> pages for Index-Translate. Pure functions over bytes: no network, no disk, no database.

A page with a usable text layer is translated as text; a page without one (scan, comic) is
rendered to PNG and sent as an image. Render size follows the official guidance for the image
client: longest edge between 512 and 2048 px (docs/image_translate.md in bilibili/Index-Translate).
"""
import base64

import pymupdf

from services.ai.index_translate import validate_image_data_url

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 50
MIN_TEXT_CHARS = 20
RENDER_DPI = 150
MIN_EDGE_PX = 512
MAX_EDGE_PX = 2048
_PDF_MAGIC = b"%PDF-"
_POINTS_PER_INCH = 72


class PdfRejectedError(ValueError):
    pass


class PdfTooLargeError(PdfRejectedError):
    pass


def open_pdf(data: bytes) -> pymupdf.Document:
    """Open an uploaded PDF from memory; reject anything that is not a plain, bounded PDF."""
    if len(data) > MAX_PDF_BYTES:
        raise PdfTooLargeError(f"PDF is too large (max {MAX_PDF_BYTES // (1024 * 1024)} MB)")
    if not data.startswith(_PDF_MAGIC):
        raise PdfRejectedError("File is not a PDF")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfRejectedError("PDF could not be read") from None
    if doc.needs_pass or doc.is_encrypted:
        doc.close()
        raise PdfRejectedError("Encrypted PDFs are not supported")
    if len(doc) == 0:
        doc.close()
        raise PdfRejectedError("PDF has no pages")
    if len(doc) > MAX_PDF_PAGES:
        doc.close()
        raise PdfTooLargeError(f"PDF has too many pages (max {MAX_PDF_PAGES})")
    return doc


def page_text(page: pymupdf.Page) -> str:
    return page.get_text("text").strip()


def classify_page(text: str) -> str:
    """'text' when the page carries a real text layer, otherwise 'image' (scan, comic, art)."""
    meaningful = sum(1 for ch in text if not ch.isspace())
    return "text" if meaningful >= MIN_TEXT_CHARS else "image"


def render_page_png_data_url(page: pymupdf.Page) -> str:
    longest_pt = max(page.rect.width, page.rect.height)
    target_px = min(max(longest_pt * RENDER_DPI / _POINTS_PER_INCH, MIN_EDGE_PX), MAX_EDGE_PX)
    zoom = target_px / longest_pt
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
    return validate_image_data_url(f"data:image/png;base64,{encoded}")
