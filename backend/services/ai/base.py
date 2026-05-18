from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict

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
        """
        pass
