import pytest
from unittest.mock import patch, MagicMock
from database import GlobalSetting
from services.ai.factory import AIProviderFactory
from services.ai.groq import GroqAdapter
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.ai.secrets import load_secrets, mask_secret


@pytest.fixture(autouse=True)
def mock_secrets():
    """Mock load_secrets to return a test groq api key."""
    with patch("services.ai.secrets.load_secrets", return_value={
        "openai_api_key": "sk-test-openai",
        "gemini_api_key": "test-gemini-key",
        "groq_api_key": "gsk_test_groq_1234567890",
    }):
        yield


class TestGroqProviderResolution:
    """Tests for Groq provider initialization via AIProviderFactory."""

    def test_groq_provider_from_db_setting(self, db_session):
        gs = GlobalSetting(llm_provider="groq", groq_model="llama-3.3-70b-versatile")
        db_session.add(gs)
        db_session.commit()

        provider = AIProviderFactory.get_provider(db_session=db_session)
        assert isinstance(provider, GroqAdapter)
        assert provider.model == "llama-3.3-70b-versatile"
        assert provider.base_url == "https://api.groq.com/openai/v1"

    def test_url_based_detection_groq(self, db_session, default_global_settings):
        provider = AIProviderFactory.get_provider(
            base_url="https://api.groq.com/openai/v1",
            db_session=db_session,
        )
        assert isinstance(provider, GroqAdapter)
        assert provider.base_url == "https://api.groq.com/openai/v1"

    def test_resolve_active_base_url_groq(self):
        gs = GlobalSetting(llm_provider="groq")
        url = resolve_active_base_url(gs)
        assert url == "https://api.groq.com/openai/v1"

    def test_resolve_active_model_groq(self):
        gs = GlobalSetting(llm_provider="groq", groq_model="mixtral-8x7b-32768")
        model = resolve_active_model(gs)
        assert model == "mixtral-8x7b-32768"

    def test_mask_groq_secret(self):
        masked = mask_secret("gsk_1234567890abcdef")
        assert masked == "gsk_...cdef"
        assert mask_secret("") == ""


class TestGroqAdapterExecution:
    """Tests for GroqAdapter execution and response parsing."""

    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        adapter = GroqAdapter(api_key="gsk_mock_123", model="llama-3.3-70b-versatile")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Halo dunia terjemahan",
                    }
                }
            ]
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            result = await adapter.chat_completion([{"role": "user", "content": "Hello"}])
            assert result == "Halo dunia terjemahan"

    @pytest.mark.asyncio
    async def test_chat_completion_with_reasoning(self):
        adapter = GroqAdapter(api_key="gsk_mock_123", model="deepseek-r1-distill-llama-70b")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "reasoning_content": "Sedang menganalisis...",
                        "content": "Hasil terjemahan R1",
                    }
                }
            ]
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            result = await adapter.chat_completion([{"role": "user", "content": "Hello"}])
            assert "<think>\nSedang menganalisis...\n</think>" in result
            assert "Hasil terjemahan R1" in result

    @pytest.mark.asyncio
    async def test_chat_completion_with_gpt_oss_reasoning(self):
        adapter = GroqAdapter(api_key="gsk_mock_123", model="openai/gpt-oss-120b")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "reasoning": "Analyzing sentence...",
                        "content": "Hasil terjemahan GPT-OSS",
                    }
                }
            ]
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            result = await adapter.chat_completion([{"role": "user", "content": "Hello"}])
            assert "<think>\nAnalyzing sentence...\n</think>" in result
            assert "Hasil terjemahan GPT-OSS" in result

    def test_qwen_chunking_and_token_capping(self):
        adapter = GroqAdapter(api_key="gsk_mock", model="qwen/qwen3.8-27b")
        assert adapter.translation_chunk_chars == 600
        assert adapter.chunk_delay_seconds == 6.0
        # When max_tokens is None or > 900, caps at 900 to avoid Groq OTPM: Limit 1000 rejection
        assert adapter._resolve_max_tokens(None) == 900
        assert adapter._resolve_max_tokens(2000) == 900
        assert adapter._resolve_max_tokens(500) == 500

    def test_gpt_oss_no_chunking_and_no_harsh_cap(self):
        adapter = GroqAdapter(api_key="gsk_mock", model="openai/gpt-oss-120b")
        assert adapter.translation_chunk_chars == 0
        assert adapter.chunk_delay_seconds == 0.0
        assert adapter._resolve_max_tokens(None) is None
        assert adapter._resolve_max_tokens(4000) == 4000
        # When max_tokens exceeds 4096, caps at 4096 to prevent prompt+output exceeding 8k TPM limit
        assert adapter._resolve_max_tokens(8000) == 4096

    def test_extract_retry_delay_from_headers(self):
        assert GroqAdapter._extract_retry_delay(headers={"retry-after": "4.5"}) == 4.5
        assert GroqAdapter._extract_retry_delay(headers={"x-ratelimit-reset-tokens": "2.3s"}) == 2.3
        assert GroqAdapter._extract_retry_delay(headers={"x-ratelimit-reset-tokens": "500ms"}) == 0.5
        assert GroqAdapter._extract_retry_delay(headers={"x-ratelimit-reset-requests": "1.2s"}) == 1.2
        assert GroqAdapter._extract_retry_delay(headers={"x-ratelimit-reset-requests": "250ms"}) == 0.5

    def test_extract_retry_delay_from_body(self):
        body = '{"error":{"message":"Rate limit reached... Please try again in 5.2s."}}'
        assert GroqAdapter._extract_retry_delay(error_body=body) == 5.2

        body_retry = '{"error":{"message":"Rate limit exceeded. retry in 3s."}}'
        assert GroqAdapter._extract_retry_delay(error_body=body_retry) == 3.0

        body_compound = '{"error":{"message":"Rate limit exceeded. try again in 1m30s."}}'
        assert GroqAdapter._extract_retry_delay(error_body=body_compound) == 90.0

    @pytest.mark.asyncio
    async def test_chat_completion_handles_null_content(self):
        adapter = GroqAdapter(api_key="gsk_mock_123", model="openai/gpt-oss-120b")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning": "Thinking about things...",
                    }
                }
            ]
        }
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            result = await adapter.chat_completion([{"role": "user", "content": "Hello"}])
            assert "<think>\nThinking about things...\n</think>" in result

    @pytest.mark.asyncio
    async def test_chat_completion_429_includes_retry_delay(self):
        adapter = GroqAdapter(api_key="gsk_mock", model="openai/gpt-oss-120b")
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "5"}
        mock_response.text = '{"error":{"message":"Rate limit reached. Please try again in 5.0s."}}'

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                await adapter.chat_completion([{"role": "user", "content": "Hello"}])
            err = str(exc_info.value)
            assert "429" in err
            assert "retry in 5.0s" in err

    def test_groq_key_exhaustion_and_rotation(self):
        import json
        from database import GlobalSetting
        from services.ai.secrets import (
            mark_key_exhausted,
            get_active_api_key,
            rotate_api_key,
            get_key_stats,
            QuotaExhaustedError,
            exhausted_groq_keys,
        )

        exhausted_groq_keys.clear()
        gs = GlobalSetting(
            llm_provider="groq",
            groq_model="openai/gpt-oss-120b",
            groq_api_keys=json.dumps(["key1", "key2"]),
            groq_active_key_index=0,
        )

        assert get_active_api_key("groq", gs) == "key1"
        stats = get_key_stats("groq", gs)
        assert stats["total"] == 2
        assert stats["exhausted"] == 0

        # Mark key1 exhausted
        mark_key_exhausted("groq", "key1", "openai/gpt-oss-120b")
        stats = get_key_stats("groq", gs)
        assert stats["exhausted"] == 1

        # Active key skips key1 and returns key2
        assert get_active_api_key("groq", gs) == "key2"

        # Mark key2 exhausted
        mark_key_exhausted("groq", "key2", "openai/gpt-oss-120b")
        # Now all keys exhausted -> QuotaExhaustedError
        with pytest.raises(QuotaExhaustedError):
            get_active_api_key("groq", gs)

        exhausted_groq_keys.clear()


