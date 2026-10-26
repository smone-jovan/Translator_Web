import pytest

from services.manga_fallback import NO_TEXT_MARKER, build_fallback_messages, translate_crop_fallback
from services.translation_guard import NonTranslationError

URL = "data:image/png;base64,AAAA"


class FakeProvider:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append((messages, temperature, max_tokens))
        return self.reply


def test_messages_carry_the_crop_and_name_the_target_language_in_one_user_turn():
    (message,) = build_fallback_messages(URL, "Indonesian")

    assert message["role"] == "user"
    text = next(p["text"] for p in message["content"] if p["type"] == "text")
    assert "Indonesian" in text and NO_TEXT_MARKER in text
    assert {"type": "image_url", "image_url": {"url": URL}} in message["content"]


@pytest.mark.asyncio
async def test_returns_the_cleaned_translation():
    provider = FakeProvider('"Aku sayang kamu~"')

    assert await translate_crop_fallback(provider, URL, "Indonesian") == "Aku sayang kamu~"
    assert provider.calls[0][1] == 0.0 and provider.calls[0][2] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", [NO_TEXT_MARKER, f"{NO_TEXT_MARKER}.", "  notext\n", ""])
async def test_no_text_marker_or_blank_means_empty_text(reply):
    assert await translate_crop_fallback(FakeProvider(reply), URL, "Indonesian") == ""


@pytest.mark.asyncio
async def test_a_reply_that_is_not_a_translation_is_rejected():
    reply = "The character in the image is written in calligraphy and the text appears to be a sound effect."

    with pytest.raises(NonTranslationError):
        await translate_crop_fallback(FakeProvider(reply), URL, "Indonesian")
