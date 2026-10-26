"""
WebP -> PNG/JPEG for the image-folder flow. Pure functions over bytes: no disk, no network.

Everything after the upload (vision model, overlay, text detector, PDF export) only understands PNG and
JPEG, so a WebP page is converted once at the entry point. Other formats pass through untouched and are
rejected later by `prepare_image_data_url`.
"""
import io
from pathlib import PurePosixPath

from PIL import Image

from services.ai.index_translate import MAX_IMAGE_BYTES
from services.image_batch import ImageRejectedError, ImageTooLargeError
from services.manga_overlay import MAX_PIXELS

__all__ = ["is_webp", "normalize_image", "normalized_name"]

JPEG_QUALITIES = (92, 80, 65)
_WHITE = (255, 255, 255)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_ALPHA_MODES = ("RGBA", "LA", "PA")


def is_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in _ALPHA_MODES or "transparency" in image.info


def _encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGBA").save(buffer, "PNG")
    return buffer.getvalue()


def _encode_jpeg(image: Image.Image) -> bytes:
    """Flatten any transparency onto white, then take the best quality that fits the size cap."""
    rgba = image.convert("RGBA")
    flat = Image.new("RGB", rgba.size, _WHITE)
    flat.paste(rgba, mask=rgba.getchannel("A"))
    for quality in JPEG_QUALITIES:
        buffer = io.BytesIO()
        flat.save(buffer, "JPEG", quality=quality)
        if buffer.tell() <= MAX_IMAGE_BYTES:
            return buffer.getvalue()
    raise ImageTooLargeError(f"Image is too large after conversion (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB)")


def normalize_image(data: bytes) -> bytes:
    """PNG/JPEG (and anything that is not WebP) is returned as is; WebP becomes JPEG, or PNG when it has alpha."""
    if not is_webp(data):
        return data
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > MAX_PIXELS:  # header only: nothing is decoded yet
            raise ImageRejectedError("WebP image has too many pixels")
        image.load()  # first frame only, even for animated files
    except ImageRejectedError:
        raise
    except Exception:
        raise ImageRejectedError("WebP image could not be read") from None

    if _has_alpha(image):
        png = _encode_png(image)
        if len(png) <= MAX_IMAGE_BYTES:
            return png
    return _encode_jpeg(image)


def normalized_name(name: str, converted: bytes) -> str:
    """Swap a `.webp` extension for the one matching the converted bytes (names stay display-only)."""
    path = PurePosixPath(name)
    if path.suffix.lower() != ".webp":
        return name
    if converted.startswith(_PNG_MAGIC):
        return str(path.with_suffix(".png"))
    if converted.startswith(_JPEG_MAGIC):
        return str(path.with_suffix(".jpg"))
    return name
