import httpx
import json

try:
    print("Connecting to LM Studio on http://localhost:1234/v1/models...")
    resp = httpx.get("http://localhost:1234/v1/models", timeout=5.0)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Connection failed: {e}")
