import pytest
from database import GlobalSetting, switch_workspace, ACTIVE_WORKSPACE
from services.ai.openrouter import OpenRouterAdapter
from services.ai.factory import AIProviderFactory
from services.ai.secrets import save_secrets, load_secrets, get_active_api_key, rotate_api_key
from services.ai.settings import resolve_active_model, resolve_active_base_url


def test_openrouter_adapter_headers():
    adapter = OpenRouterAdapter(api_key="sk-or-test-key", model="deepseek/deepseek-chat")
    headers = adapter._get_headers()
    assert headers["Authorization"] == "Bearer sk-or-test-key"
    assert headers["HTTP-Referer"] == "https://readomni.ai"
    assert headers["X-Title"] == "ReadOmni AI"
    assert adapter.model == "deepseek/deepseek-chat"


def test_openrouter_factory_resolution(db_session):
    gs = GlobalSetting(
        llm_provider="openrouter",
        openrouter_model="anthropic/claude-3.5-sonnet",
        openrouter_api_key="sk-or-factory-key"
    )
    db_session.add(gs)
    db_session.commit()

    provider = AIProviderFactory.get_provider(db_session=db_session)
    assert isinstance(provider, OpenRouterAdapter)
    assert provider.model == "anthropic/claude-3.5-sonnet"


def test_openrouter_settings_resolution(db_session):
    gs = GlobalSetting(
        llm_provider="openrouter",
        openrouter_model="meta-llama/llama-3.3-70b-instruct"
    )
    db_session.add(gs)
    db_session.commit()

    model = resolve_active_model(gs)
    assert model == "meta-llama/llama-3.3-70b-instruct"

    url = resolve_active_base_url(gs)
    assert url == "https://openrouter.ai/api/v1"


def test_openrouter_secrets_management(db_session):
    save_secrets(openrouter_api_key="sk-or-secret-val")
    secrets = load_secrets()
    assert secrets["openrouter_api_key"] == "sk-or-secret-val"

    gs = GlobalSetting(
        llm_provider="openrouter",
        openrouter_api_keys='["key1", "key2", "key3"]',
        openrouter_active_key_index=0
    )
    db_session.add(gs)
    db_session.commit()

    active_key = get_active_api_key("openrouter", gs)
    assert active_key == "key1"

    next_key = rotate_api_key("openrouter", gs)
    assert next_key == "key2"
    assert gs.openrouter_active_key_index == 1
