import httpx

try:
    print("Querying backend health check on http://localhost:8000/...")
    resp = httpx.get("http://localhost:8000/", timeout=2.0)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Backend is offline or unreachable: {e}")
