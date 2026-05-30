import pytest
from unittest.mock import patch, MagicMock
from database import GlobalSetting
from services.ai.factory import AIProviderFactory
from services.ai.lm_studio import LMStudioAdapter
from services.ai.openai import OpenAIAdapter
from services.ai.gemini import GeminiAdapter


@pytest.fixture(autouse=True)
def mock_secrets():
    """Mock load_secrets to avoid reading real .env file."""
    with patch("services.ai.secrets.load_secrets", return_value={
        "openai_api_key": "sk-test-openai",
        "gemini_api_key": "test-gemini-key",
    }):
        yield


class TestFactoryProviderResolution:
    """Tests for AIProviderFactory.get_provider() provider selection."""

    def test_defaults_to_lm_studio_when_no_settings(self, db_session):
        provider = AIProviderFactory.get_provider(db_session=db_session)
        assert isinstance(provider, LMStudioAdapter)

    def test_lm_studio_provider(self, db_session, default_global_settings):
        provider = AIProviderFactory.get_provider(db_session=db_session)
        assert isinstance(provider, LMStudioAdapter)

    def test_openai_provider(self, db_session):
        gs = GlobalSetting(llm_provider="openai", openai_model="gpt-4o")
        db_session.add(gs)
        db_session.commit()

        provider = AIProviderFactory.get_provider(db_session=db_session)
        assert isinstance(provider, OpenAIAdapter)

    def test_gemini_provider(self, db_session):
        gs = GlobalSetting(llm_provider="gemini", gemini_model="gemini-2.5-flash")
        db_session.add(gs)
        db_session.commit()

        provider = AIProviderFactory.get_provider(db_session=db_session)
        assert isinstance(provider, GeminiAdapter)

    def test_url_based_detection_gemini(self, db_session, default_global_settings):
        provider = AIProviderFactory.get_provider(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            db_session=db_session,
        )
        assert isinstance(provider, GeminiAdapter)

    def test_url_based_detection_openai(self, db_session, default_global_settings):
        provider = AIProviderFactory.get_provider(
            base_url="https://api.openai.com/v1",
            db_session=db_session,
        )
        assert isinstance(provider, OpenAIAdapter)

    def test_url_based_detection_localhost_overrides_when_different_from_db_url(self, db_session):
        gs = GlobalSetting(
            llm_provider="gemini",
            gemini_model="gemini-2.5-flash",
            lm_url="http://192.168.1.50:1234",
        )
        db_session.add(gs)
        db_session.commit()

        # localhost URL that differs from gs.lm_url -> detected as lm_studio
        provider = AIProviderFactory.get_provider(
            base_url="http://localhost:1234",
            db_session=db_session,
        )
        assert isinstance(provider, LMStudioAdapter)

    def test_url_matching_lm_url_preserves_db_provider(self, db_session):
        """When base_url == gs.lm_url, factory trusts the DB provider choice."""
        gs = GlobalSetting(
            llm_provider="gemini",
            gemini_model="gemini-2.5-flash",
            lm_url="http://localhost:1234",
        )
        db_session.add(gs)
        db_session.commit()

        provider = AIProviderFactory.get_provider(
            base_url="http://localhost:1234",
            db_session=db_session,
        )
        assert isinstance(provider, GeminiAdapter)


class TestFactoryModelNormalization:
    """Tests for Gemini model name normalization logic."""

    def _get_gemini_provider(self, db_session, model=None, gemini_model="gemini-2.5-flash"):
        gs = GlobalSetting(llm_provider="gemini", gemini_model=gemini_model)
        db_session.add(gs)
        db_session.commit()

        return AIProviderFactory.get_provider(model=model, db_session=db_session)

    def test_gemma_4_31b_normalized_to_it(self, db_session):
        provider = self._get_gemini_provider(db_session, model="gemma-4-31b")
        assert provider.model == "gemma-4-31b-it"

    def test_gemma_4_31b_it_already_normalized(self, db_session):
        provider = self._get_gemini_provider(db_session, model="gemma-4-31b-it")
        assert provider.model == "gemma-4-31b-it"

    def test_gemma_4_26b_normalized(self, db_session):
        provider = self._get_gemini_provider(db_session, model="gemma-4-26b")
        assert provider.model == "gemma-4-26b-a4b-it"

    def test_gemini_3_flash_normalized(self, db_session):
        provider = self._get_gemini_provider(db_session, model="gemini-3-flash")
        assert provider.model == "gemini-3-flash-preview"

    def test_gemini_3_flash_preview_kept(self, db_session):
        provider = self._get_gemini_provider(db_session, model="gemini-3-flash-preview")
        assert provider.model == "gemini-3-flash-preview"

    def test_gemini_3_pro_normalized(self, db_session):
        provider = self._get_gemini_provider(db_session, model="gemini-3-pro")
        assert provider.model == "gemini-3-pro-preview"

    def test_gemini_3_1_pro_normalized(self, db_session):
        provider = self._get_gemini_provider(db_session, model="gemini-3.1-pro")
        assert provider.model == "gemini-3.1-pro-preview"

    def test_non_gemini_model_falls_back_to_db(self, db_session):
        provider = self._get_gemini_provider(
            db_session,
            model="qwen2.5-7b",
            gemini_model="gemini-2.5-flash",
        )
        assert provider.model == "gemini-2.5-flash"

    def test_non_gemini_resolved_model_falls_back_to_default(self, db_session):
        provider = self._get_gemini_provider(
            db_session,
            model=None,
            gemini_model="qwen2.5",  # invalid gemini model in DB
        )
        # Should fall back to default since qwen2.5 doesn't contain gemini/gemma
        assert provider.model == "gemini-2.5-flash"


class TestFactoryOpenAIModelResolution:
    """Tests for OpenAI model resolution logic."""

    def _get_openai_provider(self, db_session, model=None, openai_model="gpt-4o"):
        gs = GlobalSetting(llm_provider="openai", openai_model=openai_model)
        db_session.add(gs)
        db_session.commit()

        return AIProviderFactory.get_provider(model=model, db_session=db_session)

    def test_respects_gpt_model(self, db_session):
        provider = self._get_openai_provider(db_session, model="gpt-4o-mini")
        assert provider.model == "gpt-4o-mini"

    def test_respects_o1_model(self, db_session):
        provider = self._get_openai_provider(db_session, model="o1-preview")
        assert provider.model == "o1-preview"

    def test_respects_o3_model(self, db_session):
        provider = self._get_openai_provider(db_session, model="o3-mini")
        assert provider.model == "o3-mini"

    def test_non_openai_model_falls_back(self, db_session):
        provider = self._get_openai_provider(
            db_session, model="gemini-2.5-flash", openai_model="gpt-4o"
        )
        assert provider.model == "gpt-4o"


class TestFactoryAdapterProperties:
    """Tests that adapters are configured with correct properties."""

    def test_lm_studio_has_model(self, db_session, default_global_settings):
        provider = AIProviderFactory.get_provider(
            model="llama3-8b", db_session=db_session
        )
        assert isinstance(provider, LMStudioAdapter)
        assert provider.model == "llama3-8b"

    def test_lm_studio_appends_v1(self, db_session, default_global_settings):
        provider = AIProviderFactory.get_provider(
            base_url="http://localhost:1234", db_session=db_session
        )
        assert "/v1" in provider.primary_url

    def test_lm_studio_dual_stack_fallback(self, db_session, default_global_settings):
        provider = AIProviderFactory.get_provider(
            base_url="http://localhost:1234", db_session=db_session
        )
        assert len(provider.urls_to_try) == 2
        assert any("127.0.0.1" in url for url in provider.urls_to_try)

    def test_openai_has_api_key(self, db_session):
        gs = GlobalSetting(llm_provider="openai", openai_model="gpt-4o")
        db_session.add(gs)
        db_session.commit()

        provider = AIProviderFactory.get_provider(
            api_key="sk-custom", db_session=db_session
        )
        assert isinstance(provider, OpenAIAdapter)
        assert provider.api_key == "sk-custom"

    def test_gemini_has_api_key(self, db_session):
        gs = GlobalSetting(llm_provider="gemini", gemini_model="gemini-2.5-flash")
        db_session.add(gs)
        db_session.commit()

        provider = AIProviderFactory.get_provider(
            api_key="gemini-custom-key", db_session=db_session
        )
        assert isinstance(provider, GeminiAdapter)
        assert provider.api_key == "gemini-custom-key"

    def test_gemini_url_always_googleapis(self, db_session):
        gs = GlobalSetting(llm_provider="gemini", gemini_model="gemini-2.5-flash")
        db_session.add(gs)
        db_session.commit()

        provider = AIProviderFactory.get_provider(db_session=db_session)
        assert "googleapis.com" in provider.base_url
