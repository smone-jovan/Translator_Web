from services.ai.settings import upstream_error_message
import httpx
import json
import logging
from typing import List, Dict, AsyncGenerator, Tuple
from services.ai.base import BaseAIProviderAdapter, TRUNCATED_MARKER, PROHIBITED_MARKER, PROHIBITED_FINISH_REASONS

logger = logging.getLogger(__name__)

class GeminiAdapter(BaseAIProviderAdapter):
    """
    Concrete adapter for the official Google Gemini API using OpenAI-compatible HTTP interface.
    No extra heavy Python SDK package dependencies required.
    """
    PROVIDER_NAME = "gemini"
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", base_url: str = None):
        self.api_key = api_key
        self.model = model
        if base_url:
            cleaned_url = base_url.rstrip("/")
            if "/v1" not in cleaned_url and "/openai" not in cleaned_url:
                cleaned_url += "/v1beta/openai"
            self.base_url = cleaned_url
        else:
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

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
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
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
                        if any(p in fr_str for p in ["prohibited", "content_filter", "safety", "blocked", "other"]):
                            pass # Let caller handle it
                        else:
                            return PROHIBITED_MARKER, "safety", data
                    
                    return content, finish_reason, data
                else:
                    raise Exception(f"'choices' was missing or empty. Response: {json.dumps(data)}")
            else:
                raise Exception(upstream_error_message(resp.status_code, resp.text))

    async def _chat_completion_with_status(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> Tuple[str, bool, bool]:
        models_to_try = [self.model]
        if self.model == "gemini-3.5-flash-lite":
            models_to_try.append("gemini-3.1-flash-lite")
        elif self.model == "gemini-3.1-flash-lite":
            models_to_try.append("gemini-3.5-flash-lite")
        
        last_error = ""
        for model in models_to_try:
            try:
                print(f"[DEBUG] Trying Gemini model: {model}")
                content, finish_reason, data = await self._try_chat_completion(
                    messages=messages, temperature=temperature, max_tokens=max_tokens, model_name=model
                )
                
                print(f"[DEBUG] Gemini API returned HTTP 200. finish_reason={finish_reason}, model={model}")
                logger.info("Gemini finish_reason=%s model=%s output_chars=%d", finish_reason, model, len(content or ""))

                if finish_reason == "length":
                    return content or "", True, False
                fr_str = str(finish_reason).lower() if finish_reason else ""
                if any(p in fr_str for p in ["prohibited", "content_filter", "safety", "blocked", "other", "recitation"]):
                    return "", False, True
                
                # Heuristic for gemini-3.1-flash-lite (~16K output limit):
                # Only flag as truncated if content is dangerously short (<100 chars) AND the input prompt is very large
                # (>2500 chars, typical for full chapter translations). This prevents short inputs like title cleaning
                # or relationship extraction from falsely returning TRUNCATED_MARKER when a short output is expected.
                total_input_len = sum(len(m.get("content", "")) for m in messages)
                if "gemini-3.1-flash-lite" in model.lower() and len(content) < 100 and total_input_len > 2500:
                    return content or "", True, False

                return content or "", False, False
                
            except Exception as e:
                last_error_str = str(e)
                last_error = f"{type(e).__name__}: {last_error_str}"
                print(f"[DEBUG] Model {model} failed: {last_error}")
                err_str = last_error.lower()
                # If Gemini threw a 400 Bad Request due to safety violation, return PROHIBITED_MARKER immediately.
                if any(p in err_str for p in ["prohibited", "content_filter", "safety", "blocked", "block reason", "policy", "rejected"]):
                    return "", False, True

                # If Gemini threw 429 Quota Exceeded, only mark key as exhausted for the day if it's a true daily limit (RPD), NOT temporary per-minute RPM limit
                is_per_minute = "perminute" in err_str or "per minute" in err_str or "requestsperminute" in err_str
                if "429" in err_str and any(q in err_str for q in ["quota", "exhausted", "resource_exhausted"]):
                    if not is_per_minute and any(d in err_str for d in ["perday", "per day", "requestsperday", "daily"]):
                        from services.ai.secrets import mark_key_exhausted
                        mark_key_exhausted("gemini", self.api_key, model)
                
                # Add delay before next attempt for flash-lite to handle rate limits
                if "gemini-3.1-flash-lite" in model.lower() and "empty content" in str(e).lower():
                    import asyncio
                    await asyncio.sleep(1.5)
                continue
        
        # If all models failed, raise the last error
        raise Exception(f"Gemini API failed after trying all fallback models. Last Error: {last_error}")

    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> str:
        content, is_truncated, is_prohibited = await self._chat_completion_with_status(
            messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        if is_prohibited:
            return PROHIBITED_MARKER
        if is_truncated and not content:
            return TRUNCATED_MARKER
        return content

    async def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> AsyncGenerator[str, None]:
        # Gemini OpenAI-compatible streaming doesn't reliably send finish_reason.
        # Fall back to non-streaming for reliable completion (especially for large outputs).
        try:
            content, is_truncated, is_prohibited = await self._chat_completion_with_status(
                messages=messages, temperature=temperature, max_tokens=max_tokens
            )
            if is_prohibited:
                yield PROHIBITED_MARKER
                return
            if content:
                yield content
            if is_truncated:
                yield TRUNCATED_MARKER
        except Exception as e:
            raise Exception(f"Gemini streaming failed: {e}")