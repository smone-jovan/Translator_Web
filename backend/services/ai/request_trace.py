"""
Diagnostic wrapper: logs one line per real request a chapter translation sends to the model
(request number, chunk position, input/output size, finish reason). It never alters the messages,
the streamed pieces or the errors, so wrapping a provider cannot change translation behaviour.
"""
from typing import AsyncGenerator, Callable, Dict, List

from services.ai.base import PROHIBITED_MARKER, TRUNCATED_MARKER


def _chars_in(messages: List[Dict[str, str]]) -> int:
    return sum(len(str(m.get("content") or "")) for m in messages)


class TracedProvider:
    def __init__(self, inner, label: str, log: Callable[[str], None] = print):
        self._inner = inner
        self._label = label
        self._log = log
        self._count = 0
        self._chunk = "-"

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def note_chunk(self, index: int | None, total: int | None = None) -> None:
        """Set by ChunkedTranslationProvider before each request; None marks a pass-through request."""
        self._chunk = "-" if index is None else f"{index}/{total}"

    def _report(self, number: int, chunk: str, chars_in: int, chars_out: int, finish: str) -> None:
        self._log(
            f"[TRACE] {self._label} request #{number} chunk={chunk} in={chars_in} out={chars_out} finish={finish}"
        )

    async def stream_chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None
    ) -> AsyncGenerator[str, None]:
        self._count += 1
        number, chunk, chars_in, chars_out, finish = self._count, self._chunk, _chars_in(messages), 0, "stop"
        try:
            async for piece in self._inner.stream_chat(messages, temperature=temperature, max_tokens=max_tokens):
                if piece == TRUNCATED_MARKER:
                    finish = "length"
                elif piece == PROHIBITED_MARKER:
                    finish = "prohibited"
                else:
                    chars_out += len(piece)
                yield piece
        except BaseException as exc:
            finish = f"error:{type(exc).__name__}"
            raise
        finally:
            self._report(number, chunk, chars_in, chars_out, finish)

    async def chat_completion(
        self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None
    ) -> str:
        self._count += 1
        number, chunk, chars_in, finish, text = self._count, self._chunk, _chars_in(messages), "stop", ""
        try:
            text = await self._inner.chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
            return text
        except BaseException as exc:
            finish = f"error:{type(exc).__name__}"
            raise
        finally:
            self._report(number, chunk, chars_in, len(text or ""), finish)
