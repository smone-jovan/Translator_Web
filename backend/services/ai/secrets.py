import os
import json

ENV_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def load_secrets() -> dict:
    """
    Load API keys safely from backend/.env.
    This file is added to .gitignore so it is never committed to Git.
    """
    secrets = {
        "openai_api_key": "",
        "gemini_api_key": ""
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
        except Exception as e:
            print(f"[SECRETS] Failed to read {ENV_FILE_PATH}: {e}")
    
    # Fallback to environment variables if not set in .env
    if not secrets["openai_api_key"]:
        secrets["openai_api_key"] = os.environ.get("OPENAI_API_KEY", "")
    if not secrets["gemini_api_key"]:
        secrets["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")
        
    return secrets


def save_secrets(openai_api_key: str | None, gemini_api_key: str | None):
    """
    Save API keys safely to backend/.env.
    """
    secrets = load_secrets()
    if openai_api_key is not None:
        secrets["openai_api_key"] = openai_api_key
    if gemini_api_key is not None:
        secrets["gemini_api_key"] = gemini_api_key
        
    try:
        # Write back to backend/.env safely
        with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("# LLM Provider API Keys (Do not commit this file to Git!)\n")
            f.write(f"OPENAI_API_KEY={secrets['openai_api_key']}\n")
            f.write(f"GEMINI_API_KEY={secrets['gemini_api_key']}\n")
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
        if gs and gs.gemini_api_keys:
            keys = json.loads(gs.gemini_api_keys)
            if keys:
                idx = gs.gemini_active_key_index if gs.gemini_active_key_index < len(keys) else 0
                return keys[idx]
        return secrets.get("gemini_api_key", "")
    
    elif provider == "openai":
        if gs and gs.openai_api_keys:
            keys = json.loads(gs.openai_api_keys)
            if keys:
                idx = gs.openai_active_key_index if gs.openai_active_key_index < len(keys) else 0
                return keys[idx]
        return secrets.get("openai_api_key", "")
    
    return ""


def rotate_api_key(provider: str, gs) -> str:
    """
    Rotate to the next API key for a provider.
    Returns the new active key.
    """
    if provider == "gemini" and gs.gemini_api_keys:
        keys = json.loads(gs.gemini_api_keys)
        if len(keys) > 1:
            gs.gemini_active_key_index = (gs.gemini_active_key_index + 1) % len(keys)
            print(f"[KEY ROTATE] Gemini: switched to key #{gs.gemini_active_key_index}")
            return keys[gs.gemini_active_key_index]
    
    elif provider == "openai" and gs.openai_api_keys:
        keys = json.loads(gs.openai_api_keys)
        if len(keys) > 1:
            gs.openai_active_key_index = (gs.openai_active_key_index + 1) % len(keys)
            print(f"[KEY ROTATE] OpenAI: switched to key #{gs.openai_active_key_index}")
            return keys[gs.openai_active_key_index]
    
    # No rotation possible, return current key
    return get_active_api_key(provider, gs)
