import httpx
import json
from typing import List, Dict, AsyncGenerator
from services.ai.base import BaseAIProviderAdapter, TRUNCATED_MARKER, PROHIBITED_MARKER, PROHIBITED_FINISH_REASONS

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
                    msg = data["choices"][0]["message"]
                    res = ""
                    if msg.get("reasoning_content"):
                        res += f"<think>\n{msg['reasoning_content']}\n</think>\n\n"
                    res += msg.get("content", "")
                    return res
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
                    
                    in_reasoning = False
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            if "[DONE]" in line:
                                break
                            try:
                                data = json.loads(line[6:])
                                choice = data["choices"][0]
                                delta = choice.get("delta", {})
                                
                                reasoning = delta.get("reasoning_content", "")
                                if reasoning:
                                    if not in_reasoning:
                                        yield "<think>\n"
                                        in_reasoning = True
                                    yield reasoning
                                    
                                content = delta.get("content", "")
                                if content:
                                    if in_reasoning:
                                        yield "\n</think>\n\n"
                                        in_reasoning = False
                                    yield content

                                finish_reason = choice.get("finish_reason")
                                if finish_reason:
                                    if in_reasoning:
                                        yield "\n</think>\n\n"
                                        in_reasoning = False
                                        
                                    if finish_reason == "length":
                                        yield TRUNCATED_MARKER
                                        return
                                    if finish_reason in PROHIBITED_FINISH_REASONS:
                                        yield PROHIBITED_MARKER
                                        return
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                    if in_reasoning:
                        yield "\n</think>\n\n"
        except Exception as e:
            raise Exception(f"OpenAI streaming failed: {e}")
