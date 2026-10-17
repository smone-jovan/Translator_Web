from urllib.parse import urlparse

from database import GlobalSetting

DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS = 22000

# Host resmi provider cloud. API key hanya boleh dikirim ke host ini (atau, khusus OpenAI,
# ke `gs.openai_url` yang dikonfigurasi pemilik). Lihat ADR-126.
OFFICIAL_PROVIDER_HOSTS = {
    "gemini": "generativelanguage.googleapis.com",
    "openrouter": "openrouter.ai",
    "openai": "api.openai.com",
}
OFFICIAL_PROVIDER_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}


def _normalize_url(url: str | None) -> str:
    return (url or "").strip().rstrip("/")


def is_trusted_provider_url(provider: str, url: str | None, gs: GlobalSetting | None = None) -> bool:
    """True bila `url` boleh menerima API key `provider`.

    Dicocokkan lewat hostname hasil parse (bukan substring), wajib https di port standar,
    tanpa kredensial di URL. Untuk OpenAI, URL yang sama persis dengan `gs.openai_url`
    (endpoint kompatibel pilihan pemilik) juga diterima.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
        port = parsed.port
    except ValueError:
        return False
    if parsed.username or parsed.password:
        return False
    official_host = OFFICIAL_PROVIDER_HOSTS.get(provider)
    if (
        official_host
        and parsed.scheme == "https"
        and (parsed.hostname or "").lower() == official_host
        and port in (None, 443)
    ):
        return True
    if provider == "openai" and gs is not None:
        configured = _normalize_url(getattr(gs, "openai_url", None))
        if configured and _normalize_url(url) == configured:
            return True
    return False


def resolve_active_model(gs: GlobalSetting | None, requested_model: str | None = None) -> str | None:
    """Return the model that belongs to the currently selected provider."""
    if not gs:
        return requested_model

    provider = getattr(gs, "llm_provider", "lm_studio")
    local_lm_model = getattr(gs, "lm_model", None)

    if provider == "gemini":
        saved_gemini = getattr(gs, "gemini_model", None) or "gemini-2.5-flash"
        if (
            requested_model
            and requested_model != local_lm_model
            and ("gemini" in requested_model.lower() or "gemma" in requested_model.lower())
        ):
            return requested_model
        return saved_gemini

    if provider == "openai":
        saved_openai = getattr(gs, "openai_model", None) or "gpt-4o-mini"
        if (
            requested_model
            and requested_model != local_lm_model
            and any(
                x in requested_model.lower()
                for x in ["gpt", "o1", "o3", "o4", "chatgpt", "openai"]
            )
        ):
            return requested_model
        return saved_openai

    if provider == "openrouter":
        saved_or_model = getattr(gs, "openrouter_model", None) or "deepseek/deepseek-chat"
        # Ignore local LM Studio model names that lack an 'author/model' slash or match gs.lm_model
        if requested_model and "/" in requested_model and requested_model != local_lm_model:
            return requested_model
        return saved_or_model

    if requested_model:
        return requested_model
    return local_lm_model


def resolve_active_base_url(gs: GlobalSetting | None, requested_url: str | None = None) -> str:
    """Return the base URL that belongs to the currently selected provider, guarding cloud providers against local URLs."""
    if not gs:
        return (requested_url or "http://localhost:1234").rstrip("/")

    provider = getattr(gs, "llm_provider", "lm_studio")
    local_lm_url = (getattr(gs, "lm_url", None) or "http://localhost:1234").rstrip("/")
    req_clean = _normalize_url(requested_url) or None

    # Provider cloud: URL dari request hanya dipakai bila host-nya tepercaya, karena
    # API key ikut terkirim ke URL tersebut (ADR-126).
    if provider == "gemini":
        if is_trusted_provider_url("gemini", req_clean):
            return req_clean
        return OFFICIAL_PROVIDER_URLS["gemini"]

    if provider == "openai":
        if is_trusted_provider_url("openai", req_clean, gs):
            return req_clean
        return _normalize_url(getattr(gs, "openai_url", None)) or OFFICIAL_PROVIDER_URLS["openai"]

    if provider == "openrouter":
        if is_trusted_provider_url("openrouter", req_clean):
            return req_clean
        return OFFICIAL_PROVIDER_URLS["openrouter"]

    if req_clean:
        return req_clean
    return local_lm_url


def get_chapter_translation_max_tokens(gs: GlobalSetting | None = None) -> int | None:
    if not gs:
        return DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS
    # Gemii models: no hard cap, but flash-lite has ~16K output limit
    if gs.llm_provider == "gemini":
        # gemini-3.1-flash-lite has a hard ~16K output token limit
        if gs.gemini_model and "gemini-3.1-flash-lite" in gs.gemini_model.lower():
            return 14000  # Leave buffer under 16K limit
        return None
    if getattr(gs, "chapter_token_cap_enabled", 1) != 1:
        return None
    cap = getattr(gs, "chapter_token_cap", DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS) or DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS
    return int(cap)


# ---------------------------------------------------------------------------
# Model-Aware Context Scaling (ADR-075)
# Returns a multiplier for context truncation limits based on model context window.
# Conservative (1x) for local LLMs, Generous (4x) for 100K+ models, Maximum (8x) for 500K+ models.
# ---------------------------------------------------------------------------

# Known context window sizes (approximate, in tokens)
_MODEL_CONTEXT_WINDOWS = {
    # Gemini models
    "gemini-2.5-flash": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
    "gemini-3-flash": 1_000_000,
    "gemini-3-pro": 1_000_000,
    "gemini-3.1-flash-lite": 500_000,
    "gemini-3.1-pro": 2_000_000,
    "gemini-3.5-flash": 1_000_000,
    "gemma-4-31b": 128_000,
    "gemma-4-26b": 128_000,
    # OpenAI models
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "o1": 200_000,
    "o3": 200_000,
    "o3-mini": 200_000,
    # Local LLM defaults (conservative)
    "qwen": 32_000,
    "deepseek": 128_000,
    "llama": 8_000,
    "mistral": 32_000,
}


def get_context_scale_for_model(model: str | None = None) -> float:
    """
    Return a context scaling multiplier based on model's known context window.

    - 1.0x for local/unknown LLMs (<100K context)
    - 4.0x for cloud models with 100K-500K context
    - 8.0x for cloud models with >500K context
    """
    if not model:
        return 1.0

    model_lower = model.lower()

    # Look up the context window
    context_window = None
    for model_key, window in _MODEL_CONTEXT_WINDOWS.items():
        if model_key in model_lower:
            context_window = window
            break

    if context_window is None:
        # Unknown model — use conservative defaults
        # If it looks like a cloud model, give it generous limits
        if any(prefix in model_lower for prefix in ["gemini", "gpt", "o1", "o3", "claude"]):
            return 4.0
        return 1.0

    if context_window >= 500_000:
        return 8.0
    elif context_window >= 100_000:
        return 4.0
    else:
        return 1.0
