from services.ai.settings import upstream_error_message
import httpx
import json
import re
from typing import List, Dict, AsyncGenerator
from services.ai.base import BaseAIProviderAdapter, TRUNCATED_MARKER, PROHIBITED_MARKER, PROHIBITED_FINISH_REASONS


class GroqAdapter(BaseAIProviderAdapter):
    """
    Concrete adapter for the official Groq Cloud API using OpenAI-compatible HTTP post endpoints.
    Allows high-speed LPU inference with Llama, Mixtral, Qwen, and DeepSeek models.
    """
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b", base_url: str = "https://api.groq.com/openai/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

        m_lower = (model or "").lower()
        if "qwen" in m_lower:
            # Qwen has strict 1,000 output tokens per minute on Groq on-demand tier.
            # 600 Chinese characters produces ~700-800 Indonesian tokens, safely within the 900 token cap.
            self.translation_chunk_chars = 600
            self.chunk_delay_seconds = 6.0
        elif "allam" in m_lower:
            self.translation_chunk_chars = 2500
            self.chunk_delay_seconds = 3.0
        else:
            self.translation_chunk_chars = 0
            self.chunk_delay_seconds = 0.0

    def _resolve_max_tokens(self, max_tokens: int | None) -> int | None:
        """Cap max_tokens according to Groq model limits (e.g. Qwen 1,000 OTPM ceiling, 8k TPM)."""
        m_lower = (self.model or "").lower()
        if "qwen" in m_lower:
            if max_tokens is None:
                return 900
            return min(max_tokens, 900)
        elif "allam" in m_lower:
            if max_tokens is None:
                return 4096
            return min(max_tokens, 4096)
        if max_tokens is not None and max_tokens > 4096:
            return 4096
        return max_tokens

    @staticmethod
    def _extract_retry_delay(headers: httpx.Headers | dict | None = None, error_body: str | bytes | None = None) -> float | None:
        """Extract retry delay in seconds from HTTP headers or Groq error response body."""
        if headers:
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
            if retry_after:
                try:
                    return max(0.5, float(retry_after))
                except (ValueError, TypeError):
                    pass
            for hdr_name in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
                val_hdr = headers.get(hdr_name)
                if val_hdr:
                    match = re.search(r"(\d+(?:\.\d+)?)\s*(ms|s|m)?", str(val_hdr), re.IGNORECASE)
                    if match:
                        val = float(match.group(1))
                        unit = (match.group(2) or "s").lower()
                        if unit == "ms":
                            return max(0.5, val / 1000.0)
                        elif unit == "m":
                            return val * 60.0
                        return max(0.5, val)

        if error_body:
            text = error_body if isinstance(error_body, str) else error_body.decode("utf-8", errors="replace")
            compound_match = re.search(r"(?:try again in|retry in|wait)\s*(\d+(?:\.\d+)?)\s*m\s*(\d+(?:\.\d+)?)\s*s", text, re.IGNORECASE)
            if compound_match:
                mins = float(compound_match.group(1))
                secs = float(compound_match.group(2))
                return max(0.5, mins * 60.0 + secs)
            match = re.search(r"(?:try again in|retry in|wait)\s*(\d+(?:\.\d+)?)\s*(ms|s|m)?", text, re.IGNORECASE)
            if match:
                val = float(match.group(1))
                unit = (match.group(2) or "s").lower()
                if unit == "ms":
                    return max(0.5, val / 1000.0)
                elif unit == "m":
                    return val * 60.0
                return max(0.5, val)
        return None

    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        resolved_max_tokens = self._resolve_max_tokens(max_tokens)
        if resolved_max_tokens is not None:
            payload["max_tokens"] = resolved_max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    res = ""
                    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
                    if reasoning:
                        res += f"<think>\n{reasoning}\n</think>\n\n"
                    res += msg.get("content") or ""
                    return res
                retry_delay = self._extract_retry_delay(resp.headers, resp.text)
                delay_str = f" (retry in {retry_delay:.1f}s)" if retry_delay is not None else ""
                raise Exception(f"{upstream_error_message(resp.status_code, resp.text)}{delay_str}")
        except Exception as e:
            if "Groq connection failed" in str(e):
                raise
            raise Exception(f"Groq connection failed: {e}")

    async def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int | None = None) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        resolved_max_tokens = self._resolve_max_tokens(max_tokens)
        if resolved_max_tokens is not None:
            payload["max_tokens"] = resolved_max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_bytes = await response.aread()
                        error_text = error_bytes.decode("utf-8", errors="replace")
                        retry_delay = self._extract_retry_delay(response.headers, error_text)
                        delay_str = f" (retry in {retry_delay:.1f}s)" if retry_delay is not None else ""
                        raise Exception(f"{upstream_error_message(response.status_code, error_text)}{delay_str}")
                    
                    in_reasoning = False
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            if "[DONE]" in line:
                                break
                            try:
                                data = json.loads(line[6:])
                                choice = data["choices"][0]
                                delta = choice.get("delta", {})
                                
                                reasoning = delta.get("reasoning") or delta.get("reasoning_content") or ""
                                if reasoning:
                                    if not in_reasoning:
                                        yield "<think>\n"
                                        in_reasoning = True
                                    yield reasoning
                                    
                                content = delta.get("content") or ""
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
                            except Exception:
                                continue
                    if in_reasoning:
                        yield "\n</think>\n\n"
                        in_reasoning = False
        except Exception as e:
            if "Groq stream failed" in str(e):
                raise
            raise Exception(f"Groq stream failed: {e}")
