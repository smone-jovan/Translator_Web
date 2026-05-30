import pytest
from database import GlobalSetting
from services.ai.settings import (
    resolve_active_model,
    resolve_active_base_url,
    get_chapter_translation_max_tokens,
    DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS,
)


class TestResolveActiveModel:
    """Tests for resolve_active_model() -- picks the model matching the active provider."""

    def test_returns_none_when_no_settings(self):
        assert resolve_active_model(None) is None

    def test_returns_requested_model_when_no_settings(self):
        assert resolve_active_model(None, "gpt-4o") == "gpt-4o"

    def test_lm_studio_provider_returns_lm_model(self, db_session, default_global_settings):
        result = resolve_active_model(default_global_settings)
        assert result == "qwen2.5-7b-instruct"

    def test_lm_studio_provider_prefers_requested_model(self, db_session, default_global_settings):
        result = resolve_active_model(default_global_settings, "llama3-8b")
        assert result == "llama3-8b"

    def test_gemini_provider_returns_gemini_model(self, db_session):
        gs = GlobalSetting(
            llm_provider="gemini",
            gemini_model="gemini-2.5-flash",
            openai_model="gpt-4o",
            lm_model="qwen2.5",
        )
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_model(gs)
        assert result == "gemini-2.5-flash"

    def test_gemini_provider_respects_gemini_model_name(self, db_session):
        gs = GlobalSetting(
            llm_provider="gemini",
            gemini_model="gemini-2.5-flash",
            openai_model="gpt-4o",
        )
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_model(gs, "gemma-4-31b")
        assert result == "gemma-4-31b"

    def test_gemini_provider_rejects_non_gemini_model(self, db_session):
        gs = GlobalSetting(
            llm_provider="gemini",
            gemini_model="gemini-2.5-flash",
        )
        db_session.add(gs)
        db_session.commit()

        # gpt-4o is not a gemini model -> falls back to gs.gemini_model
        result = resolve_active_model(gs, "gpt-4o")
        assert result == "gemini-2.5-flash"

    def test_openai_provider_returns_openai_model(self, db_session):
        gs = GlobalSetting(
            llm_provider="openai",
            openai_model="gpt-4o-mini",
            gemini_model="gemini-2.5-flash",
        )
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_model(gs)
        assert result == "gpt-4o-mini"

    def test_openai_provider_respects_gpt_model_name(self, db_session):
        gs = GlobalSetting(
            llm_provider="openai",
            openai_model="gpt-4o",
        )
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_model(gs, "o3-mini")
        assert result == "o3-mini"

    def test_openai_provider_rejects_non_openai_model(self, db_session):
        gs = GlobalSetting(
            llm_provider="openai",
            openai_model="gpt-4o",
        )
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_model(gs, "gemini-2.5-flash")
        assert result == "gpt-4o"


class TestResolveActiveBaseUrl:
    """Tests for resolve_active_base_url()."""

    def test_returns_requested_url_when_provided(self):
        result = resolve_active_base_url(None, "http://custom:8080")
        assert result == "http://custom:8080"

    def test_strips_trailing_slash(self):
        result = resolve_active_base_url(None, "http://custom:8080/")
        assert result == "http://custom:8080"

    def test_defaults_to_localhost_when_no_settings(self):
        assert resolve_active_base_url(None) == "http://localhost:1234"

    def test_lm_studio_returns_lm_url(self, db_session, default_global_settings):
        result = resolve_active_base_url(default_global_settings)
        assert result == "http://localhost:1234"

    def test_gemini_returns_googleapis_url(self, db_session):
        gs = GlobalSetting(llm_provider="gemini")
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_base_url(gs)
        assert "generativelanguage.googleapis.com" in result

    def test_openai_returns_openai_url(self, db_session):
        gs = GlobalSetting(llm_provider="openai", openai_url="https://api.openai.com/v1")
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_base_url(gs)
        assert result == "https://api.openai.com/v1"

    def test_openai_custom_url(self, db_session):
        gs = GlobalSetting(llm_provider="openai", openai_url="https://custom.openai.proxy/v1/")
        db_session.add(gs)
        db_session.commit()

        result = resolve_active_base_url(gs)
        assert result == "https://custom.openai.proxy/v1"


class TestGetChapterTranslationMaxTokens:
    """Tests for get_chapter_translation_max_tokens()."""

    def test_returns_default_when_no_settings(self):
        assert get_chapter_translation_max_tokens(None) == DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS

    def test_returns_none_when_cap_disabled(self, db_session):
        gs = GlobalSetting(chapter_token_cap_enabled=0)
        db_session.add(gs)
        db_session.commit()

        assert get_chapter_translation_max_tokens(gs) is None

    def test_returns_custom_cap(self, db_session):
        gs = GlobalSetting(chapter_token_cap_enabled=1, chapter_token_cap=15000)
        db_session.add(gs)
        db_session.commit()

        assert get_chapter_translation_max_tokens(gs) == 15000

    def test_returns_default_when_cap_is_none(self, db_session):
        gs = GlobalSetting(chapter_token_cap_enabled=1, chapter_token_cap=None)
        db_session.add(gs)
        db_session.commit()

        assert get_chapter_translation_max_tokens(gs) == DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS
