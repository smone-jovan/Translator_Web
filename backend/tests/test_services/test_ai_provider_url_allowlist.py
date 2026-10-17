"""
API key tidak boleh terkirim ke URL pilihan klien (ADR-122 risiko sisa, ditutup di ADR-126).

Provider cloud hanya boleh memakai host resmi (Gemini, OpenRouter) atau, untuk OpenAI,
host resmi / `gs.openai_url` yang dikonfigurasi pemilik. URL lain dari request diabaikan.
"""

from unittest.mock import MagicMock

import pytest

from database import GlobalSetting
from services.ai.factory import AIProviderFactory
from services.ai.settings import resolve_active_base_url

GEMINI_OFFICIAL = "https://generativelanguage.googleapis.com/v1beta/openai"
OPENROUTER_OFFICIAL = "https://openrouter.ai/api/v1"
OPENAI_OFFICIAL = "https://api.openai.com/v1"


def _gs(provider: str, **kw) -> GlobalSetting:
    return GlobalSetting(
        llm_provider=provider,
        lm_url="http://localhost:1234",
        openai_url=kw.pop("openai_url", OPENAI_OFFICIAL),
        gemini_model="gemini-2.5-flash",
        openai_model="gpt-4o",
        openrouter_model="deepseek/deepseek-chat",
        **kw,
    )


# --- resolve_active_base_url -------------------------------------------------

@pytest.mark.parametrize(
    "requested",
    [
        "https://evil.example/v1",
        "https://evil.example/openai/v1",
        "https://api.openai.com.evil.example/v1",
        "http://192.168.1.50:8080/v1",
    ],
)
def test_openai_ignores_untrusted_requested_url(requested):
    assert resolve_active_base_url(_gs("openai"), requested) == OPENAI_OFFICIAL


def test_openai_accepts_owner_configured_custom_url():
    gs = _gs("openai", openai_url="https://my-proxy.example/v1")
    assert resolve_active_base_url(gs, "https://my-proxy.example/v1/") == "https://my-proxy.example/v1"
    assert resolve_active_base_url(gs, "https://evil.example/v1") == "https://my-proxy.example/v1"
    # Host resmi tetap boleh walau pemilik memakai URL kustom.
    assert resolve_active_base_url(gs, OPENAI_OFFICIAL) == OPENAI_OFFICIAL


@pytest.mark.parametrize(
    "requested",
    [
        "https://evil.example/gemini",
        "https://gemini.evil.example/v1beta/openai",
        "https://evil.example/googleapis.com/v1",
        "http://generativelanguage.googleapis.com/v1beta/openai",  # bukan https
    ],
)
def test_gemini_ignores_untrusted_requested_url(requested):
    assert resolve_active_base_url(_gs("gemini"), requested) == GEMINI_OFFICIAL


def test_gemini_accepts_official_host():
    assert resolve_active_base_url(_gs("gemini"), GEMINI_OFFICIAL + "/") == GEMINI_OFFICIAL


@pytest.mark.parametrize(
    "requested",
    [
        "https://evil.example/openrouter.ai/api/v1",
        "https://openrouter.ai.evil.example/api/v1",
    ],
)
def test_openrouter_ignores_untrusted_requested_url(requested):
    assert resolve_active_base_url(_gs("openrouter"), requested) == OPENROUTER_OFFICIAL


def test_lm_studio_still_accepts_lan_url():
    assert resolve_active_base_url(_gs("lm_studio"), "http://192.168.1.10:1234") == "http://192.168.1.10:1234"


# --- AIProviderFactory: kunci hanya dikirim ke host tepercaya ------------------

def _db_with(gs) -> MagicMock:
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = gs
    return db


@pytest.mark.parametrize("provider", ["lm_studio", "gemini", "openai", "openrouter"])
@pytest.mark.parametrize(
    "base_url",
    [
        "https://evil.example/gemini",
        "https://evil.example/openrouter/api/v1",
        "https://evil.example/openai/v1",
        "https://evil.example/googleapis.com/v1beta/openai",
        "https://evil.example/openrouter.ai/api/v1",
        "https://evil.example/api.openai.com/v1",
    ],
)
def test_factory_never_pairs_api_key_with_untrusted_url(monkeypatch, provider, base_url):
    monkeypatch.setattr("services.ai.secrets.get_active_api_key", lambda *a, **k: "sk-SECRET")
    adapter = AIProviderFactory.get_provider(base_url=base_url, model=None, db_session=_db_with(_gs(provider)))
    api_key = getattr(adapter, "api_key", None)
    target = getattr(adapter, "base_url", None) or getattr(adapter, "primary_url", "")
    assert not (api_key and "evil.example" in target), (
        f"{type(adapter).__name__} would send its API key to {target}"
    )


# --- Route translate: lm_url dari request lewat resolver ----------------------

@pytest.mark.asyncio
async def test_translate_get_lm_url_does_not_forward_untrusted_url_for_cloud_provider():
    from routers.translate import get_lm_url

    url = await get_lm_url("https://evil.example/openai/v1", _db_with(_gs("openai")))
    assert url == OPENAI_OFFICIAL


@pytest.mark.asyncio
async def test_translate_get_lm_url_keeps_lan_url_for_lm_studio():
    from routers.translate import get_lm_url

    url = await get_lm_url("http://192.168.1.10:1234/", _db_with(_gs("lm_studio")))
    assert url == "http://192.168.1.10:1234"
