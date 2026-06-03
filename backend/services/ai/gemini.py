import httpx
import json
from typing import List, Dict, AsyncGenerator
from services.ai.base import BaseAIProviderAdapter, TRUNCATED_MARKER, PROHIBITED_MARKER, PROHIBITED_FINISH_REASONS

class GeminiAdapter(BaseAIProviderAdapter):
    """
    Concrete adapter for the official Google Gemini API using OpenAI-compatible HTTP interface.
    No extra heavy Python SDK package dependencies required.
    """
    FALLBACK_MODELS = ["gemini-2.5-flash"]  # Fallback chain for gemini-3.1-flash-lite
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def _try_chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None, model_name: str | None = None) -> str:
        """Single attempt at chat completion with specified model."""
        use_model = model_name or self.model
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        # Note: 'thinking' parameter not supported on OpenAI-compatible endpoint
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    first_choice = data["choices"][0]
                    finish_reason = first_choice.get("finish_reason")
                    
                    content = None
                    if "message" in first_choice:
                        message = first_choice["message"]
                        content = message.get("content") or message.get("text") or ""
                    elif "content" in first_choice:
                        content = first_choice["content"]
                    
                    # Check for empty content (Gemini-3.1-flash-lite sometimes returns HTTP 200 with no content)
                    if content is None or (isinstance(content, str) and not content.strip()):
                        fr_str = str(finish_reason).lower() if finish_reason else ""
                        if any(p in fr_str for p in ["prohibited", "content_filter", "safety", "blocked"]):
                            pass # Let caller handle it
                        else:
                            raise Exception(f"API returned empty content. finish_reason={finish_reason}")
                    
                    return content, finish_reason, data
                else:
                    raise Exception(f"'choices' was missing or empty. Response: {json.dumps(data)}")
            else:
                raise Exception(f"HTTP {resp.status_code}: {resp.text}")

    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> str:
        # Try primary model, then fallback models if this is gemini-3.1-flash-lite
        models_to_try = [self.model]
        if "gemini-3.1-flash-lite" in self.model.lower():
            models_to_try.extend(self.FALLBACK_MODELS)
        
        last_error = ""
        for model in models_to_try:
            try:
                print(f"[DEBUG] Trying Gemini model: {model}")
                content, finish_reason, data = await self._try_chat_completion(
                    messages=messages, temperature=temperature, max_tokens=max_tokens, model_name=model
                )
                
                print(f"[DEBUG] Gemini API returned HTTP 200. finish_reason={finish_reason}, model={model}")
                
                usage = data.get("usage", {})
                if finish_reason == "length":
                    return TRUNCATED_MARKER
                fr_str = str(finish_reason).lower() if finish_reason else ""
                if any(p in fr_str for p in ["prohibited", "content_filter", "safety", "blocked"]):
                    return PROHIBITED_MARKER
                
                # Heuristic for gemini-3.1-flash-lite (~16K output limit):
                # Only flag as truncated if content is dangerously short (<100 chars) with no clear ending
                if "gemini-3.1-flash-lite" in model.lower() and len(content) < 100:
                    return TRUNCATED_MARKER
                
                return content
                
            except Exception as e:
                last_error = str(e)
                print(f"[DEBUG] Model {model} failed: {e}")
                err_str = last_error.lower()
                # If Gemini threw a 400 Bad Request due to safety violation, return PROHIBITED_MARKER immediately.
                if any(p in err_str for p in ["prohibited", "content_filter", "safety", "blocked", "block reason"]):
                    return PROHIBITED_MARKER
                
                # Add delay before next attempt for flash-lite to handle rate limits
                if "gemini-3.1-flash-lite" in model.lower() and "empty content" in str(e).lower():
                    import asyncio
                    await asyncio.sleep(1.5)
                continue
        
        # If all models failed, raise the last error
        raise Exception(f"Gemini API failed after trying all fallback models. Last Error: {last_error}")

    async def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> AsyncGenerator[str, None]:
        # Gemini OpenAI-compatible streaming doesn't reliably send finish_reason.
        # Fall back to non-streaming for reliable completion (especially for large outputs).
        try:
            content = await self.chat_completion(messages=messages, temperature=temperature, max_tokens=max_tokens)
            yield content
        except Exception as e:
            raise Exception(f"Gemini streaming failed: {e}")