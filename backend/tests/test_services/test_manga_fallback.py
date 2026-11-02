import pytest

from services.ai.base import Completion
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


class FakeDetailedProvider(FakeProvider):
    """LM Studio-like provider: accepts extra payload keys."""

    async def chat_completion_detailed(self, messages, temperature=0.3, max_tokens=None, extra=None):
        self.calls.append((messages, temperature, max_tokens, extra))
        return Completion(self.reply, "stop")


@pytest.mark.asyncio
async def test_a_think_block_is_dropped_before_the_guard():
    reply = "<think>\nThe image shows a girl blushing; the bubble says 好きだよ.\n</think>\n\nAku sayang kamu~"

    assert await translate_crop_fallback(FakeProvider(reply), URL, "Indonesian") == "Aku sayang kamu~"


@pytest.mark.asyncio
async def test_a_reply_cut_off_while_thinking_is_rejected_not_marked_as_no_text():
    reply = "<think>\nLet me read the bubble carefully. The characters are"

    with pytest.raises(NonTranslationError):
        await translate_crop_fallback(FakeProvider(reply), URL, "Indonesian")


@pytest.mark.asyncio
async def test_thinking_is_switched_off_when_the_provider_accepts_extra_payload():
    provider = FakeDetailedProvider("Aku sayang kamu~")

    assert await translate_crop_fallback(provider, URL, "Indonesian") == "Aku sayang kamu~"
    assert provider.calls[0][3] == {"chat_template_kwargs": {"enable_thinking": False}}


@pytest.mark.asyncio
async def test_a_reply_that_is_not_a_translation_is_rejected():
    reply = "The character in the image is written in calligraphy and the text appears to be a sound effect."

    with pytest.raises(NonTranslationError):
        await translate_crop_fallback(FakeProvider(reply), URL, "Indonesian")
