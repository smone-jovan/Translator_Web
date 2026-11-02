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

