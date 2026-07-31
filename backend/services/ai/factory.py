from sqlalchemy.orm import Session
from sqlalchemy import select

from database import GlobalSetting
from services.ai.base import BaseAIProviderAdapter

class AIProviderFactory:
    """
    Factory to resolve and create the appropriate swappable AI provider adapter.
    Reads global configurations dynamically from database or parameter injections,
    with secure API key lookup from the ignored .env file.
    """
    
    @staticmethod
    def get_provider(
        base_url: str = None,
        model: str = None,
        api_key: str = None,
        db_session: Session = None
    ) -> BaseAIProviderAdapter:
        """
        Create a provider instance directly from parameters, with smart fallbacks to database settings.
        """
        local_session = None
        if db_session is None:
            from database import SessionLocal
            local_session = SessionLocal()
            db_session = local_session

        try:
            # Load active global settings
            gs_stmt = select(GlobalSetting)
            gs = db_session.execute(gs_stmt).scalar_one_or_none()
            
            provider = gs.llm_provider if gs else "lm_studio"
            from services.ai.secrets import get_active_api_key
            
            # If the user explicitly passed a custom base_url, respect it
            if base_url:
                # If gs is present and base_url matches the setting's lm_url, do not override provider
                if gs and base_url == gs.lm_url:
                    pass
                else:
                    if "generativelanguage.googleapis.com" in base_url or "gemini" in base_url.lower():
                        provider = "gemini"
                    elif "openrouter.ai" in base_url.lower() or "openrouter" in base_url.lower():
                        provider = "openrouter"
                    elif "api.openai.com" in base_url or "openai" in base_url.lower():
                        provider = "openai"
                    elif "localhost" in base_url or "127.0.0.1" in base_url:
                        provider = "lm_studio"

            # 1. Google Gemini Provider
            if provider == "gemini":
                from services.ai.gemini import GeminiAdapter
                # Smart model resolution: only respect passed model if it contains 'gemini' or 'gemma' and NO slash (e.g. google/gemma)
                is_gemini_model = model and ("gemini" in model.lower() or "gemma" in model.lower()) and "/" not in model
                resolved_model = model if is_gemini_model else (gs.gemini_model if gs else "gemini-2.5-flash")
                
                # Double check to prevent local models like qwen from leaking as gemini model
                if not ("gemini" in resolved_model.lower() or "gemma" in resolved_model.lower()):
                    resolved_model = "gemini-2.5-flash"
                
                # Normalize popular Gemini/Gemma models to their official Google API identifiers
                model_lower = resolved_model.lower()
                if "gemma-4-31b" in model_lower and not model_lower.endswith("-it"):
                    resolved_model = "gemma-4-31b-it"
                elif "gemma-4-26b" in model_lower and not model_lower.endswith("-it"):
                    resolved_model = "gemma-4-26b-a4b-it"
                elif "gemini-3-flash" in model_lower and not ("preview" in model_lower or "image" in model_lower):
                    resolved_model = "gemini-3-flash-preview"
                elif "gemini-3-pro" in model_lower and not ("preview" in model_lower or "image" in model_lower):
                    resolved_model = "gemini-3-pro-preview"
                elif "gemini-3.1-pro" in model_lower and not "preview" in model_lower:
                    resolved_model = "gemini-3.1-pro-preview"
                elif "gemini-3.1-flash-lite" in model_lower:
                    resolved_model = "gemini-3.1-flash-lite"
                
                print(f"[DEBUG] get_provider -> provider is gemini. Input model: '{model}', resolved_model: '{resolved_model}', database gemini_model: '{gs.gemini_model if gs else 'N/A'}'")
                resolved_key = api_key or get_active_api_key("gemini", gs)
                # Prevent sending Gemini cloud requests to local URL
                resolved_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                if base_url and ("googleapis.com" in base_url or "gemini" in base_url.lower()):
                    resolved_url = base_url
                return GeminiAdapter(api_key=resolved_key, model=resolved_model, base_url=resolved_url)

            # 2. OpenRouter Cloud Provider
            elif provider == "openrouter":
                from services.ai.openrouter import OpenRouterAdapter
                resolved_model = model or (gs.openrouter_model if gs else "deepseek/deepseek-chat")
                resolved_key = api_key or get_active_api_key("openrouter", gs) or "sk-or-dummy"
                resolved_url = "https://openrouter.ai/api/v1"
                if base_url and "openrouter.ai" in base_url.lower():
                    resolved_url = base_url
                return OpenRouterAdapter(api_key=resolved_key, model=resolved_model, base_url=resolved_url)
                
            # 3. OpenAI Cloud Provider
            elif provider == "openai":
                from services.ai.openai import OpenAIAdapter
                # Smart model resolution: only respect passed model if it is an OpenAI model name
                is_openai_model = model and any(x in model.lower() for x in ["gpt", "o1", "o3", "openai"])
                resolved_model = model if is_openai_model else (gs.openai_model if gs else "gpt-4o")
                
                if not any(x in resolved_model.lower() for x in ["gpt", "o1", "o3", "openai"]):
                    resolved_model = "gpt-4o"
                
                resolved_key = api_key or get_active_api_key("openai", gs) or "sk-dummy"
                resolved_url = gs.openai_url if (gs and gs.openai_url) else "https://api.openai.com/v1"
                if base_url and ("api.openai.com" in base_url or "openai" in base_url.lower()):
                    resolved_url = base_url
                return OpenAIAdapter(api_key=resolved_key, model=resolved_model, base_url=resolved_url)
                
            # 4. LM Studio / Local LLM Provider
            else:
                from services.ai.lm_studio import LMStudioAdapter
                resolved_url = base_url or (gs.lm_url if gs else "http://localhost:1234")
                resolved_model = model or (gs.lm_model if gs else None)
                return LMStudioAdapter(base_url=resolved_url, model=resolved_model)
        finally:
            if local_session:
                local_session.close()

    @staticmethod
    def get_default_provider(db_session: Session) -> BaseAIProviderAdapter:
        """
        Resolves the active LLM client based on the GlobalSetting persisted in the SQLite DB.
        """
        return AIProviderFactory.get_provider(db_session=db_session)
