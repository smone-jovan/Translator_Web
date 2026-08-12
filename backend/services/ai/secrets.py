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


# Global in-memory round-robin counters to distribute requests evenly across healthy keys
_key_rotation_counters: dict[str, int] = {
    "gemini": 0,
    "openai": 0,
    "openrouter": 0
}

def get_active_api_key(provider: str, gs=None, auto_advance: bool = False) -> str:
    """
    Get the active API key for a provider with true round-robin load balancing.
    Automatically skips keys that have exceeded their daily quota.
    """
    secrets = load_secrets()
    
    if provider == "gemini":
        _clear_stale_exhausted_keys()
        model = gs.gemini_model if gs else ""
        if gs and gs.gemini_api_keys:
            try:
                keys = json.loads(gs.gemini_api_keys)
            except Exception:
                keys = []
            if keys:
                # Find all healthy keys that haven't hit their daily quota
                healthy_keys = [
                    k for k in keys 
                    if (f"{k}::{model}" if model else k) not in exhausted_gemini_keys
                ]
                if not healthy_keys:
                    model_str = f" for model '{model}'" if model else ""
                    raise QuotaExhaustedError(f"All available Gemini API keys ({len(keys)} keys) have hit their daily quota limit{model_str}.")
                
                if hasattr(gs, 'gemini_active_key_index') and gs.gemini_active_key_index is not None:
                    chosen_idx = gs.gemini_active_key_index % len(healthy_keys)
                else:
                    current_count = _key_rotation_counters["gemini"]
                    chosen_idx = current_count % len(healthy_keys)
                    if auto_advance:
                        _key_rotation_counters["gemini"] = (current_count + 1) % 1_000_000
                
                chosen_key = healthy_keys[chosen_idx]
                return chosen_key
        
        single_key = secrets.get("gemini_api_key", "")
        if single_key:
            dict_key = f"{single_key}::{model}" if model else single_key
            if dict_key in exhausted_gemini_keys:
                model_str = f" for model '{model}'" if model else ""
                raise QuotaExhaustedError(f"The single Gemini API key has hit its daily quota limit{model_str}.")
        return single_key
    
    elif provider == "openai":
        if gs and gs.openai_api_keys:
            try:
                keys = json.loads(gs.openai_api_keys)
            except Exception:
                keys = []
            if keys:
                if hasattr(gs, 'openai_active_key_index') and gs.openai_active_key_index is not None:
                    chosen_idx = gs.openai_active_key_index % len(keys)
                else:
                    current_count = _key_rotation_counters["openai"]
                    chosen_idx = current_count % len(keys)
                    if auto_advance:
                        _key_rotation_counters["openai"] = (current_count + 1) % 1_000_000
                return keys[chosen_idx]
        return secrets.get("openai_api_key", "")

    elif provider == "openrouter":
        if gs and gs.openrouter_api_keys:
            try:
                keys = json.loads(gs.openrouter_api_keys)
            except Exception:
                keys = []
            if keys:
                if hasattr(gs, 'openrouter_active_key_index') and gs.openrouter_active_key_index is not None:
                    chosen_idx = gs.openrouter_active_key_index % len(keys)
                else:
                    current_count = _key_rotation_counters["openrouter"]
                    chosen_idx = current_count % len(keys)
                    if auto_advance:
                        _key_rotation_counters["openrouter"] = (current_count + 1) % 1_000_000
                return keys[chosen_idx]
        return secrets.get("openrouter_api_key", "")
    
    return ""


def rotate_api_key(provider: str, gs) -> str:
    """
    Explicitly advance to the next API key for a provider.
    Returns the new active key and updates the active key index on gs.
    """
    if gs:
        if provider == "gemini" and gs.gemini_api_keys:
            try:
                keys = json.loads(gs.gemini_api_keys)
                if keys:
                    gs.gemini_active_key_index = ((gs.gemini_active_key_index or 0) + 1) % len(keys)
                    _key_rotation_counters["gemini"] = gs.gemini_active_key_index
            except Exception:
                pass
        elif provider == "openai" and gs.openai_api_keys:
            try:
                keys = json.loads(gs.openai_api_keys)
                if keys:
                    gs.openai_active_key_index = ((gs.openai_active_key_index or 0) + 1) % len(keys)
                    _key_rotation_counters["openai"] = gs.openai_active_key_index
            except Exception:
                pass
        elif provider == "openrouter" and gs.openrouter_api_keys:
            try:
                keys = json.loads(gs.openrouter_api_keys)
                if keys:
                    gs.openrouter_active_key_index = ((gs.openrouter_active_key_index or 0) + 1) % len(keys)
                    _key_rotation_counters["openrouter"] = gs.openrouter_active_key_index
            except Exception:
                pass
    else:
        if provider in _key_rotation_counters:
            _key_rotation_counters[provider] = (_key_rotation_counters[provider] + 1) % 1_000_000

    print(f"[KEY ROTATE] {provider.capitalize()}: shifted to next key round-robin (counter={_key_rotation_counters.get(provider, 0)})")
    return get_active_api_key(provider, gs, auto_advance=False)
