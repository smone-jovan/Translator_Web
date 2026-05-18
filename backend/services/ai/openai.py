import httpx
import json
from typing import List, Dict, AsyncGenerator
from services.ai.base import BaseAIProviderAdapter

class OpenAIAdapter(BaseAIProviderAdapter):
    """
    Concrete adapter for the official OpenAI API using standard HTTP post endpoints.
    Allows easy routing to external LLMs and cloud-based models.
    """
    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                raise Exception(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            raise Exception(f"OpenAI connection failed: {e}")

    async def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise Exception(f"HTTP {response.status_code}: {error_text.decode()}")
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            if "[DONE]" in line:
                                break
                            try:
                                data = json.loads(line[6:])
                                content = data["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
        except Exception as e:
            raise Exception(f"OpenAI streaming failed: {e}")
