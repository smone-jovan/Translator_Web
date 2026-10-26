import io

import pytest
from PIL import Image

from services import image_normalize
from services.ai.index_translate import validate_image_data_url
from services.image_batch import ImageRejectedError, ImageTooLargeError, prepare_image_data_url
from services.image_normalize import normalize_image, normalized_name

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


def make_webp(size=(300, 400), mode="RGB", color=(120, 60, 200), **save):
    image = Image.new(mode, size, color if mode == "RGB" else color + (128,))
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", **save)
    return buffer.getvalue()


def make_other(fmt):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), (1, 2, 3)).save(buffer, fmt)
    return buffer.getvalue()


def test_png_and_jpeg_pass_through_unchanged():
    png = make_other("PNG")
    jpeg = make_other("JPEG")

    assert normalize_image(png) is png
    assert normalize_image(jpeg) is jpeg


def test_plain_webp_becomes_jpeg_that_the_model_validator_accepts():
    result = normalize_image(make_webp())

    assert result.startswith(JPEG_MAGIC)
    assert Image.open(io.BytesIO(result)).size == (300, 400)
    assert validate_image_data_url(prepare_image_data_url(result))


def test_webp_with_alpha_becomes_png_keeping_transparency():
    result = normalize_image(make_webp(mode="RGBA", color=(10, 20, 30)))

    assert result.startswith(PNG_MAGIC)
    assert Image.open(io.BytesIO(result)).mode == "RGBA"
    assert validate_image_data_url(prepare_image_data_url(result))


def test_alpha_webp_falls_back_to_white_composited_jpeg_when_png_is_too_big(monkeypatch):
    monkeypatch.setattr(image_normalize, "MAX_IMAGE_BYTES", 200)
    data = make_webp(size=(64, 64), mode="RGBA", color=(0, 0, 0))

    result = normalize_image(data)

    assert result.startswith(JPEG_MAGIC) or len(result) <= 200
    if result.startswith(JPEG_MAGIC):
        corner = Image.open(io.BytesIO(result)).convert("RGB").getpixel((0, 0))
        assert min(corner) > 100  # half-transparent black over white is grey, not black


def test_animated_webp_uses_first_frame():
    frames = [Image.new("RGB", (50, 80), color) for color in ((255, 0, 0), (0, 0, 255))]
    buffer = io.BytesIO()
    frames[0].save(buffer, "WEBP", save_all=True, append_images=frames[1:], duration=100, lossless=True)

    result = normalize_image(buffer.getvalue())

    pixel = Image.open(io.BytesIO(result)).convert("RGB").getpixel((10, 10))
    assert pixel[0] > 200 and pixel[2] < 60


def test_conversion_is_deterministic():
    data = make_webp()

    assert normalize_image(data) == normalize_image(data)


def test_corrupt_webp_is_rejected_with_a_clear_error():
    corrupt = b"RIFF\x10\x00\x00\x00WEBPVP8 garbage-bytes"

    with pytest.raises(ImageRejectedError, match="WebP"):
        normalize_image(corrupt)


def test_webp_with_too_many_pixels_is_rejected_before_decoding(monkeypatch):
    monkeypatch.setattr(image_normalize, "MAX_PIXELS", 1000)

    with pytest.raises(ImageRejectedError, match="pixels"):
        normalize_image(make_webp(size=(100, 100)))


def test_webp_that_cannot_fit_the_size_cap_is_too_large(monkeypatch):
    monkeypatch.setattr(image_normalize, "MAX_IMAGE_BYTES", 50)

    with pytest.raises(ImageTooLargeError):
        normalize_image(make_webp(size=(200, 200)))


@pytest.mark.parametrize("fmt", ["GIF", "BMP"])
def test_other_formats_are_left_alone_and_still_rejected(fmt):
    data = make_other(fmt)

    assert normalize_image(data) is data
    with pytest.raises(ImageRejectedError):
        prepare_image_data_url(data)


def test_unconverted_webp_is_rejected_by_the_validator_with_a_webp_hint():
    with pytest.raises(ImageRejectedError, match="WebP"):
        prepare_image_data_url(make_webp())


@pytest.mark.parametrize(
    ("name", "data", "expected"),
    [
        ("p1.webp", "jpeg", "p1.jpg"),
        ("p1.WEBP", "png", "p1.png"),
        ("p1.png", "png", "p1.png"),
        ("noext", "jpeg", "noext"),
    ],
)
def test_normalized_name_follows_the_converted_format(name, data, expected):
    payload = PNG_MAGIC if data == "png" else JPEG_MAGIC

    assert normalized_name(name, payload) == expected
