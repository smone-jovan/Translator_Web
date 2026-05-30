from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict

# Sentinel yielded by streaming adapters when the AI hit max_tokens (finish_reason="length").
# The background translator detects this and auto-continues the translation.
TRUNCATED_MARKER = "[[TRUNCATED]]"

# Sentinel yielded when the AI refused the request (finish_reason="prohibited", "content_filter", "safety", etc.).
# The background translator detects this and skips saving — resets chapter to idle.
PROHIBITED_MARKER = "[[PROHIBITED]]"

# Recognized prohibited/filtered finish reasons from AI providers
PROHIBITED_FINISH_REASONS = {"prohibited", "content_filter", "safety", "blocked"}


class BaseAIProviderAdapter(ABC):
    """
    Port definition for AI Provider clients (e.g. LM Studio, OpenAI, Anthropic).
    Concrete adapters implement this to decouple completion requests from core logic.
    """
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a non-streaming chat completion request and return the text content.
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a streaming chat completion request and yield text tokens.
        If the response is truncated (finish_reason="length"), yields TRUNCATED_MARKER at the end.
        """
        pass
