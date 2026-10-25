import pytest

from services.ai.base import TRUNCATED_MARKER
from services.ai.chunking import ChunkedTranslationProvider
from services.ai.request_trace import TracedProvider


class FakeProvider:
    translation_temperature = 0.0

    def __init__(self, pieces=("Hello", " world"), fail=False):
        self.pieces = list(pieces)
        self.fail = fail
        self.calls = []

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        for piece in self.pieces:
            yield piece
        if self.fail:
            raise RuntimeError("boom")

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        return "".join(self.pieces)


async def _drain(provider, messages):
    return [piece async for piece in provider.stream_chat(messages)]


@pytest.mark.asyncio
async def test_numbers_requests_and_reports_sizes():
    lines = []
    traced = TracedProvider(FakeProvider(), "ch7", log=lines.append)
    messages = [{"role": "user", "content": "abcd"}]

    await _drain(traced, messages)
    await _drain(traced, messages)

    assert "ch7 request #1" in lines[0] and "in=4" in lines[0] and "out=11" in lines[0] and "finish=stop" in lines[0]
    assert "request #2" in lines[1]


@pytest.mark.asyncio
async def test_reports_length_finish_and_still_passes_the_marker_through():
    lines = []
    traced = TracedProvider(FakeProvider(("part", TRUNCATED_MARKER)), "ch1", log=lines.append)

    pieces = await _drain(traced, [{"role": "user", "content": "x"}])

    assert pieces == ["part", TRUNCATED_MARKER]
    assert "finish=length" in lines[0]
    assert "out=4" in lines[0]


@pytest.mark.asyncio
async def test_logs_and_reraises_errors():
    lines = []
    traced = TracedProvider(FakeProvider(fail=True), "ch1", log=lines.append)

    with pytest.raises(RuntimeError):
        await _drain(traced, [{"role": "user", "content": "x"}])

    assert "finish=error:RuntimeError" in lines[0]


@pytest.mark.asyncio
async def test_chat_completion_is_traced_and_returns_the_text():
    lines = []
    traced = TracedProvider(FakeProvider(("ab", "cd")), "ch1", log=lines.append)

    assert await traced.chat_completion([{"role": "user", "content": "xyz"}]) == "abcd"
    assert "in=3" in lines[0] and "out=4" in lines[0]


def test_other_attributes_pass_through():
    assert TracedProvider(FakeProvider(), "ch1", log=lambda _: None).translation_temperature == 0.0


@pytest.mark.asyncio
async def test_chunked_requests_report_their_chunk_position():
    lines = []
    inner = FakeProvider()
    traced = TracedProvider(inner, "ch1", log=lines.append)
    chunked = ChunkedTranslationProvider(traced, 10)
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "aaaaaaaa\nbbbbbbbb\ncccccccc"}]

    pieces = await _drain(chunked, messages)

    assert len(inner.calls) == 3  # chunking behaviour is unchanged
    assert [("chunk=1/3" in lines[0]), ("chunk=2/3" in lines[1]), ("chunk=3/3" in lines[2])] == [True] * 3
    assert "".join(pieces).count("Hello world") == 3


@pytest.mark.asyncio
async def test_unchunked_requests_report_no_chunk():
    lines = []
    chunked = ChunkedTranslationProvider(TracedProvider(FakeProvider(), "ch1", log=lines.append), 1000)

    await _drain(chunked, [{"role": "system", "content": "s"}, {"role": "user", "content": "short"}])

    assert "chunk=-" in lines[0]
