import base64

import pytest

from services.ai.index_translate import (
    MAX_IMAGE_BYTES,
    build_index_translate_image_messages,
    validate_image_data_url,
)

PIXEL = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
PNG_URL = f"data:image/png;base64,{PIXEL}"


class TestValidateImageDataUrl:
    @pytest.mark.parametrize("mime", ["png", "jpeg", "webp"])
    def test_accepts_supported_image_types(self, mime):
        url = f"data:image/{mime};base64,{PIXEL}"
        assert validate_image_data_url(url) == url

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "https://example.com/a.png",
            "file:///etc/passwd",
            "data:text/html;base64,PGh0bWw+",
            "data:image/svg+xml;base64,PHN2Zz4=",
            "data:image/gif;base64,R0lGOD==",
            "data:image/png;base64,",
            "data:image/png;base64,not base64 !!",
            "data:image/png,rawbytes",
        ],
    )
    def test_rejects_anything_else(self, bad):
        with pytest.raises(ValueError):
            validate_image_data_url(bad)

    def test_rejects_oversized_image(self):
        big = base64.b64encode(b"x" * (MAX_IMAGE_BYTES + 1)).decode()
        with pytest.raises(ValueError, match="too large"):
            validate_image_data_url(f"data:image/png;base64,{big}")


class TestImageMessages:
    def test_builds_readme_image_prompt_for_indonesian(self):
        assert build_index_translate_image_messages(PNG_URL, "Indonesian") == [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请将图片中的文本翻译为印尼语，直接输出翻译结果，不要进行任何解释。",
                    },
                    {"type": "image_url", "image_url": {"url": PNG_URL}},
                ],
            }
        ]

    def test_other_targets_fall_back_to_english(self):
        messages = build_index_translate_image_messages(PNG_URL, "English")
        assert "翻译为英语" in messages[0]["content"][0]["text"]
