from database import GlobalSetting

DEFAULT_CHAPTER_TRANSLATION_MAX_TOKENS = 22000


def resolve_active_model(gs: GlobalSetting | None, requested_model: str | None = None) -> str | None:
    """Return the model that belongs to the currently selected provider."""
    if not gs:
        return requested_model

    provider = getattr(gs, "llm_provider", "lm_studio")
    if provider == "gemini":
        if requested_model and ("gemini" in requested_model.lower() or "gemma" in requested_model.lower()):
            return requested_model
        return getattr(gs, "gemini_model", None)
    if provider == "openai":
        if requested_model and any(x in requested_model.lower() for x in ["gpt", "o1", "o3", "openai"]):
            return requested_model
        return getattr(gs, "openai_model", None)
    if requested_model:
        return requested_model
    return getattr(gs, "lm_model", None)


def resolve_active_base_url(gs: GlobalSetting | None, requested_url: str | None = None) -> str:
    """Return the base URL that belongs to the currently selected provider."""
    if requested_url:
        return requested_url.rstrip("/")
    if not gs:
        return "http://localhost:1234"

    provider = getattr(gs, "llm_provider", "lm_studio")
    if provider == "gemini":
        return "https://generativelanguage.googleapis.com/v1beta/openai"
    if provider == "openai":
        return (getattr(gs, "openai_url", None) or "https://api.openai.com/v1").rstrip("/")
    return (getattr(gs, "lm_url", None) or "http://localhost:1234").rstrip("/")


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
