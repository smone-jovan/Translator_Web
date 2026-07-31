import httpx
import json
from typing import List, Dict, AsyncGenerator
from services.ai.base import BaseAIProviderAdapter, TRUNCATED_MARKER, PROHIBITED_MARKER, PROHIBITED_FINISH_REASONS

class LMStudioAdapter(BaseAIProviderAdapter):
    """
    Concrete adapter for LM Studio (Local LLM) using OpenAI-compatible HTTP interface.
    Handles robust connectivity and dual-stack localhost/127.0.0.1 fallback.
    """
    def __init__(self, base_url: str = "http://localhost:1234", model: str = None):
        self.model = model
        self.primary_url = base_url.rstrip("/")
        if "/v1" not in self.primary_url:
            self.primary_url += "/v1"
            
        self.urls_to_try = [self.primary_url]
        if "localhost" in self.primary_url:
            self.urls_to_try.append(self.primary_url.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in self.primary_url:
            self.urls_to_try.append(self.primary_url.replace("127.0.0.1", "localhost"))

    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> str:
        payload = {
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        else:
            payload["max_tokens"] = -1
        if self.model:
            payload["model"] = self.model

        last_error = ""
        for url in self.urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    resp = await client.post(f"{url}/chat/completions", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        msg = data["choices"][0]["message"]
                        res = ""
                        if msg.get("reasoning_content"):
                            res += f"<think>\n{msg['reasoning_content']}\n</think>\n\n"
                        res += msg.get("content", "")
                        return res
                    last_error = f"HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                last_error = str(e)
                continue
        
        raise Exception(f"LM Studio connection failed. Error: {last_error}")

    async def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> AsyncGenerator[str, None]:
        payload = {
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        # If max_tokens is huge or None, omit it entirely so LM Studio handles it natively
        if self.model:
            payload["model"] = self.model

        last_error = ""
        success = False
        
        for url in self.urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    async with client.stream("POST", f"{url}/chat/completions", json=payload) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            last_error = f"HTTP {response.status_code}: {error_text.decode()}"
                            continue
                        
                        success = True
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
                        return
            except Exception as e:
                last_error = str(e)
                continue
                
        if not success:
            raise Exception(f"LM Studio streaming failed. Tried {', '.join(self.urls_to_try)}. Error: {last_error}")
