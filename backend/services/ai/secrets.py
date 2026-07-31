import os
import json
import datetime

ENV_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

class QuotaExhaustedError(Exception):
    """Raised when all available API keys for a provider have hit their RPD quota limits."""
    pass

# Global RAM-based blacklist for API keys that hit their daily RPD limit
# Format: { "api_key::model_name": "YYYY-MM-DD" }
exhausted_gemini_keys: dict[str, str] = {}

def _clear_stale_exhausted_keys():
    """Clears keys from the blacklist if their stored date is no longer today."""
    today = datetime.date.today().isoformat()
    stale_keys = [k for k, date_str in exhausted_gemini_keys.items() if date_str != today]
    for k in stale_keys:
        del exhausted_gemini_keys[k]

def mark_key_exhausted(provider: str, api_key: str, model: str = ""):
    """Marks an API key as exhausted for the current day."""
    if provider == "gemini" and api_key:
        today = datetime.date.today().isoformat()
        dict_key = f"{api_key}::{model}" if model else api_key
        exhausted_gemini_keys[dict_key] = today
        model_str = f" for model '{model}'" if model else ""
        print(f"[QUOTA] Gemini API key starting with '{api_key[:8]}...' has been marked as EXHAUSTED{model_str} until {today} ends.")

def get_key_stats(provider: str, gs) -> dict:
    """Returns total keys and currently exhausted keys for a provider."""
    stats = {"total": 1, "exhausted": 0}
    if provider == "gemini":
        _clear_stale_exhausted_keys()
        model = gs.gemini_model if gs else ""
        if gs and gs.gemini_api_keys:
            try:
                keys = json.loads(gs.gemini_api_keys)
                if isinstance(keys, list) and len(keys) > 0:
                    stats["total"] = len(keys)
                    stats["exhausted"] = sum(1 for k in keys if (f"{k}::{model}" if model else k) in exhausted_gemini_keys)
            except Exception:
                pass
        else:
            # Single key fallback
            single_key = load_secrets().get("gemini_api_key", "")
            if single_key:
                dict_key = f"{single_key}::{model}" if model else single_key
                if dict_key in exhausted_gemini_keys:
                    stats["exhausted"] = 1
    return stats



def load_secrets() -> dict:
    """
    Load API keys safely from backend/.env.
    This file is added to .gitignore so it is never committed to Git.
    """
    secrets = {
        "openai_api_key": "",
        "gemini_api_key": "",
        "openrouter_api_key": ""
    }
    if os.path.exists(ENV_FILE_PATH):
        try:
            with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if key == "OPENAI_API_KEY":
                            secrets["openai_api_key"] = val
                        elif key == "GEMINI_API_KEY":
                            secrets["gemini_api_key"] = val
                        elif key == "OPENROUTER_API_KEY":
                            secrets["openrouter_api_key"] = val
        except Exception as e:
            print(f"[SECRETS] Failed to read {ENV_FILE_PATH}: {e}")
    
    # Fallback to environment variables if not set in .env
    if not secrets["openai_api_key"]:
        secrets["openai_api_key"] = os.environ.get("OPENAI_API_KEY", "")
    if not secrets["gemini_api_key"]:
        secrets["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")
    if not secrets["openrouter_api_key"]:
        secrets["openrouter_api_key"] = os.environ.get("OPENROUTER_API_KEY", "")
        
    return secrets


def save_secrets(openai_api_key: str | None = None, gemini_api_key: str | None = None, openrouter_api_key: str | None = None):
    """
    Save API keys safely to backend/.env.
    """
    secrets = load_secrets()
    if openai_api_key is not None:
        secrets["openai_api_key"] = openai_api_key
    if gemini_api_key is not None:
        secrets["gemini_api_key"] = gemini_api_key
    if openrouter_api_key is not None:
        secrets["openrouter_api_key"] = openrouter_api_key
        
    try:
        # Write back to backend/.env safely
        with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("# LLM Provider API Keys (Do not commit this file to Git!)\n")
            f.write(f"OPENAI_API_KEY={secrets['openai_api_key']}\n")
            f.write(f"GEMINI_API_KEY={secrets['gemini_api_key']}\n")
            f.write(f"OPENROUTER_API_KEY={secrets['openrouter_api_key']}\n")
        print(f"[SECRETS] API keys saved successfully to {ENV_FILE_PATH}")
    except Exception as e:
        print(f"[SECRETS] Failed to write to {ENV_FILE_PATH}: {e}")
        raise e


def get_active_api_key(provider: str, gs=None) -> str:
    """
    Get the active API key for a provider.
    Checks multiple keys first, then falls back to single key.
    """
    secrets = load_secrets()
    
    if provider == "gemini":
        _clear_stale_exhausted_keys()
        model = gs.gemini_model if gs else ""
        if gs and gs.gemini_api_keys:
            keys = json.loads(gs.gemini_api_keys)
            if keys:
                # Find the next available non-exhausted key starting from current index
                start_idx = gs.gemini_active_key_index if gs.gemini_active_key_index < len(keys) else 0
                for offset in range(len(keys)):
                    idx = (start_idx + offset) % len(keys)
                    dict_key = f"{keys[idx]}::{model}" if model else keys[idx]
                    if dict_key not in exhausted_gemini_keys:
                        # Found a healthy key, optionally update the index if we skipped
                        if offset > 0:
                            gs.gemini_active_key_index = idx
                        return keys[idx]
                # If we get here, ALL keys are exhausted for this model
                model_str = f" for model '{model}'" if model else ""
                raise QuotaExhaustedError(f"All available Gemini API keys have hit their daily quota limit{model_str}.")
        
        single_key = secrets.get("gemini_api_key", "")
        if single_key:
            dict_key = f"{single_key}::{model}" if model else single_key
            if dict_key in exhausted_gemini_keys:
                model_str = f" for model '{model}'" if model else ""
                raise QuotaExhaustedError(f"The single Gemini API key has hit its daily quota limit{model_str}.")
        return single_key
    
    elif provider == "openai":
        if gs and gs.openai_api_keys:
            keys = json.loads(gs.openai_api_keys)
            if keys:
                idx = gs.openai_active_key_index if gs.openai_active_key_index < len(keys) else 0
                return keys[idx]
        return secrets.get("openai_api_key", "")

    elif provider == "openrouter":
        if gs and gs.openrouter_api_keys:
            keys = json.loads(gs.openrouter_api_keys)
            if keys:
                idx = gs.openrouter_active_key_index if gs.openrouter_active_key_index < len(keys) else 0
                return keys[idx]
        return secrets.get("openrouter_api_key", "")
    
    return ""


def rotate_api_key(provider: str, gs) -> str:
    """
    Rotate to the next API key for a provider.
    Returns the new active key.
    """
    if provider == "gemini" and gs.gemini_api_keys:
        _clear_stale_exhausted_keys()
        model = gs.gemini_model if gs else ""
        keys = json.loads(gs.gemini_api_keys)
        if len(keys) > 1:
            start_idx = gs.gemini_active_key_index
            for offset in range(1, len(keys) + 1):
                idx = (start_idx + offset) % len(keys)
                dict_key = f"{keys[idx]}::{model}" if model else keys[idx]
                if dict_key not in exhausted_gemini_keys:
                    gs.gemini_active_key_index = idx
                    print(f"[KEY ROTATE] Gemini: switched to key #{gs.gemini_active_key_index}")
                    return keys[idx]
            # All keys are exhausted
            raise QuotaExhaustedError("All available Gemini API keys have hit their daily quota limit.")
    
    elif provider == "openai" and gs.openai_api_keys:
        keys = json.loads(gs.openai_api_keys)
        if len(keys) > 1:
            gs.openai_active_key_index = (gs.openai_active_key_index + 1) % len(keys)
            print(f"[KEY ROTATE] OpenAI: switched to key #{gs.openai_active_key_index}")
            return keys[gs.openai_active_key_index]

    elif provider == "openrouter" and gs.openrouter_api_keys:
        keys = json.loads(gs.openrouter_api_keys)
        if len(keys) > 1:
            gs.openrouter_active_key_index = (gs.openrouter_active_key_index + 1) % len(keys)
            print(f"[KEY ROTATE] OpenRouter: switched to key #{gs.openrouter_active_key_index}")
            return keys[gs.openrouter_active_key_index]
    
    # No rotation possible, return current key
    return get_active_api_key(provider, gs)
