import pytest

from services.ai.base import TRUNCATED_MARKER
from services.ai.chunking import ChunkedTranslationProvider, maybe_chunk, split_into_chunks
from services.ai.lm_studio import LMStudioAdapter
from services.ai.openai import OpenAIAdapter


class FakeProvider:
    translation_temperature = 0.0
    translation_chunk_chars = 20

    def __init__(self, truncate_on_call=None):
        self.calls = []
        self.truncate_on_call = truncate_on_call

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        n = len(self.calls)
        yield f"T{n}:" + messages[-1]["content"][:3]
        if self.truncate_on_call == n:
            yield TRUNCATED_MARKER

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        return f"T{len(self.calls)}"


async def collect(gen):
    return [piece async for piece in gen]


class TestSplitIntoChunks:
    def test_keeps_paragraphs_whole_and_within_limit(self):
        text = "aaaa\nbbbb\ncccc\ndddd\neeee"
        chunks = split_into_chunks(text, 10)
        assert all(len(c) <= 10 for c in chunks)
        assert "\n".join(chunks) == text

    def test_oversized_paragraph_splits_at_sentence_end(self):
        text = "第一句话。第二句话。第三句话。第四句话。"
        chunks = split_into_chunks(text, 10)
        assert all(len(c) <= 10 for c in chunks)
        assert "".join(chunks) == text
        assert chunks[0].endswith("。")

    def test_unbroken_text_is_hard_split(self):
        chunks = split_into_chunks("x" * 25, 10)
        assert [len(c) for c in chunks] == [10, 10, 5]

    def test_short_text_is_single_chunk(self):
        assert split_into_chunks("hello", 100) == ["hello"]

    def test_blank_text_yields_no_chunks(self):
        assert split_into_chunks("   \n ", 10) == []


class TestChunkedTranslationProvider:
    @pytest.mark.asyncio
    async def test_long_user_message_is_sent_in_chunks_with_same_system_prompt(self):
        inner = FakeProvider()
        provider = ChunkedTranslationProvider(inner, 20)
        messages = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "aaaaaaaa\nbbbbbbbb\ncccccccc\ndddddddd"},
        ]
        pieces = await collect(provider.stream_chat(messages))
        assert len(inner.calls) == 2
        assert all(c[0] == {"role": "system", "content": "SYS"} for c in inner.calls)
        assert all(len(c[1]["content"]) <= 20 for c in inner.calls)
        assert "".join(pieces).startswith("T1:")
        assert "T2:" in "".join(pieces)

    @pytest.mark.asyncio
    async def test_short_user_message_passes_through_unchanged(self):
        inner = FakeProvider()
        provider = ChunkedTranslationProvider(inner, 20)
        messages = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "short"}]
        await collect(provider.stream_chat(messages))
        assert inner.calls == [messages]

    @pytest.mark.asyncio
    async def test_continuation_conversation_passes_through_unchanged(self):
        inner = FakeProvider()
        provider = ChunkedTranslationProvider(inner, 20)
        messages = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "x" * 100},
            {"role": "assistant", "content": "... tail"},
            {"role": "user", "content": "continue"},
        ]
        await collect(provider.stream_chat(messages))
        assert inner.calls == [messages]

    @pytest.mark.asyncio
    async def test_truncation_stops_remaining_chunks_and_surfaces_marker(self):
        inner = FakeProvider(truncate_on_call=1)
        provider = ChunkedTranslationProvider(inner, 20)
        messages = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "aaaaaaaa\nbbbbbbbb\ncccccccc\ndddddddd"},
        ]
        pieces = await collect(provider.stream_chat(messages))
        assert len(inner.calls) == 1
        assert pieces[-1] == TRUNCATED_MARKER

    @pytest.mark.asyncio
    async def test_chat_completion_joins_chunk_results(self):
        inner = FakeProvider()
        provider = ChunkedTranslationProvider(inner, 20)
        messages = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "aaaaaaaa\nbbbbbbbb\ncccccccc\ndddddddd"},
        ]
        result = await provider.chat_completion(messages)
        assert result == "T1\n\nT2"

    def test_attributes_are_delegated_to_inner_provider(self):
        provider = ChunkedTranslationProvider(FakeProvider(), 20)
        assert provider.translation_temperature == 0.0


class TestMaybeChunk:
    def test_lm_studio_is_wrapped(self):
        assert isinstance(maybe_chunk(LMStudioAdapter()), ChunkedTranslationProvider)

    def test_other_providers_are_not_wrapped(self):
        provider = OpenAIAdapter.__new__(OpenAIAdapter)
        assert maybe_chunk(provider) is provider
