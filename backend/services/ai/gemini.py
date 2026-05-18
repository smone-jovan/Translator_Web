import httpx
import json
from typing import List, Dict, AsyncGenerator
from services.ai.base import BaseAIProviderAdapter

class GeminiAdapter(BaseAIProviderAdapter):
    """
    Concrete adapter for the official Google Gemini API using OpenAI-compatible HTTP interface.
    No extra heavy Python SDK package dependencies required.
    """
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"):
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
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"[DEBUG] Gemini API returned HTTP 200. Body: {json.dumps(data)}")
                    if "choices" in data and len(data["choices"]) > 0:
                        first_choice = data["choices"][0]
                        if "message" in first_choice:
                            return first_choice["message"]["content"]
                        elif "finish_reason" in first_choice:
                            reason = first_choice["finish_reason"]
                            raise Exception(f"Request blocked or stopped by Gemini API filters. Finish reason: {reason}")
                        else:
                            raise Exception(f"API choice has no message or finish_reason. Response: {json.dumps(data)}")
                    else:
                        raise Exception(f"API returned HTTP 200 but 'choices' was missing or empty. Response: {json.dumps(data)}")
                print(f"[DEBUG] Gemini API returned HTTP {resp.status_code}. Body: {resp.text}")
                raise Exception(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            raise Exception(f"Gemini API connection failed: {e}")

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
            async with httpx.AsyncClient(timeout=120.0) as client:
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
            raise Exception(f"Gemini streaming failed: {e}")
