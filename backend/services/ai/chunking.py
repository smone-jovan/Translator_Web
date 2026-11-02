import re
from typing import AsyncGenerator, Callable, Dict, List

from services.ai.base import PROHIBITED_MARKER, TRUNCATED_MARKER

CHUNK_SEPARATOR = "\n\n"
_SENTENCE_END = re.compile(r"(?<=[。！？!?….])")


def _split_long_paragraph(paragraph: str, limit: int) -> List[str]:
    """Pack sentences greedily up to `limit`; hard-split any sentence that is itself too long."""
    pieces: List[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > limit:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:limit])
            sentence = sentence[limit:]
        if current and len(current) + len(sentence) > limit:
            pieces.append(current)
            current = ""
        current += sentence
    if current:
        pieces.append(current)
    return pieces


def split_into_chunks(text: str, limit: int) -> List[str]:
    """Split text on paragraph boundaries into chunks of at most `limit` chars."""
    if not text.strip():
        return []
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    current = ""
    for paragraph in text.split("\n"):
        if len(paragraph) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_paragraph(paragraph, limit))
            continue
        if current and len(current) + 1 + len(paragraph) > limit:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


class ChunkedTranslationProvider:
    """
    Wraps a provider so a long [system, user] translation request is sent as several
    small requests. Small local models lose the instructions on very long inputs and
    start echoing the system prompt instead of translating.
    Any other conversation shape (e.g. continuation rounds) passes through unchanged.
    """

    def __init__(
        self,
        inner,
        max_chars: int,
        source_text: str | None = None,
        message_builder: Callable[[str], List[Dict[str, str]]] | None = None,
    ):
        self._inner = inner
        self._max_chars = max_chars
        self._source_text = source_text
        self._message_builder = message_builder

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def _note_chunk(self, index: int | None, total: int | None = None) -> None:
        """Tell a diagnostic wrapper (request_trace) which chunk the next request is; no-op otherwise."""
        note = getattr(self._inner, "note_chunk", None)
        if note:
            note(index, total)

    def _builder_requests(self, messages: List[Dict[str, str]]):
        """Prompt is built around the source text (no separate system message): rebuild it per chunk."""
        if messages != self._message_builder(self._source_text):
            return None
        chunks = split_into_chunks(self._source_text, self._max_chars)
        if len(chunks) <= 1:
            return None
        return [self._message_builder(chunk) for chunk in chunks]

    def _chunk_requests(self, messages: List[Dict[str, str]]):
        if self._message_builder is not None and self._source_text is not None:
            return self._builder_requests(messages)
        if len(messages) != 2 or messages[0].get("role") != "system" or messages[1].get("role") != "user":
            return None
        chunks = split_into_chunks(messages[1]["content"], self._max_chars)
        if len(chunks) <= 1:
            return None
        return [[messages[0], {**messages[1], "content": chunk}] for chunk in chunks]

    async def stream_chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None
    ) -> AsyncGenerator[str, None]:
        requests = self._chunk_requests(messages)
        if requests is None:
            self._note_chunk(None)
            async for piece in self._inner.stream_chat(messages, temperature=temperature, max_tokens=max_tokens):
                yield piece
            return

        for index, request in enumerate(requests):
            if index:
                yield CHUNK_SEPARATOR
                chunk_delay = getattr(self._inner, "chunk_delay_seconds", 0.0)
                if chunk_delay > 0:
                    import asyncio
                    await asyncio.sleep(chunk_delay)
            self._note_chunk(index + 1, len(requests))
            chunk_yielded = False
            for chunk_attempt in range(3):
                try:
                    async for piece in self._inner.stream_chat(request, temperature=temperature, max_tokens=max_tokens):
                        chunk_yielded = True
                        yield piece
                        if piece in (TRUNCATED_MARKER, PROHIBITED_MARKER):
                            return
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    is_retryable = any(p in err_str for p in ("429", "503", "502", "rate limit", "too many requests", "timeout"))
                    if is_retryable and chunk_attempt < 2:
                        if chunk_yielded:
                            # If tokens were already sent downstream, we cannot re-stream from start without duplicating text
                            raise
                        import asyncio, re
                        match = re.search(r"(?:retry in|try again in|wait)\s*(\d+(?:\.\d+)?)\s*(ms|s|m)?", err_str)
                        wait_sec = 6.0
                        if match:
                            v = float(match.group(1))
                            u = (match.group(2) or "s").lower()
                            wait_sec = v / 1000.0 if u == "ms" else (v * 60.0 if u == "m" else v)
                            wait_sec += 1.0
                        await asyncio.sleep(max(wait_sec, 4.0))
                        continue
                    raise

    async def chat_completion(
        self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None
    ) -> str:
        requests = self._chunk_requests(messages)
        if requests is None:
            self._note_chunk(None)
            return await self._inner.chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
        results = []
        for index, request in enumerate(requests):
            if index:
                chunk_delay = getattr(self._inner, "chunk_delay_seconds", 0.0)
                if chunk_delay > 0:
                    import asyncio
                    await asyncio.sleep(chunk_delay)
            self._note_chunk(index + 1, len(requests))
            for chunk_attempt in range(3):
                try:
                    res = await self._inner.chat_completion(request, temperature=temperature, max_tokens=max_tokens)
                    results.append(res)
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    is_retryable = any(p in err_str for p in ("429", "503", "502", "rate limit", "too many requests", "timeout"))
                    if is_retryable and chunk_attempt < 2:
                        import asyncio, re
                        match = re.search(r"(?:retry in|try again in|wait)\s*(\d+(?:\.\d+)?)\s*(ms|s|m)?", err_str)
                        wait_sec = 6.0
                        if match:
                            v = float(match.group(1))
                            u = (match.group(2) or "s").lower()
                            wait_sec = v / 1000.0 if u == "ms" else (v * 60.0 if u == "m" else v)
                            wait_sec += 1.0
                        await asyncio.sleep(max(wait_sec, 4.0))
                        continue
                    raise
        return CHUNK_SEPARATOR.join(results)


def maybe_chunk(provider, source_text: str | None = None, message_builder=None):
    """Wrap `provider` when it declares a translation chunk size; otherwise return it as is."""
    limit = getattr(provider, "translation_chunk_chars", 0)
    if not limit:
        return provider
    return ChunkedTranslationProvider(provider, limit, source_text=source_text, message_builder=message_builder)
