import httpx
import json
import time

try:
    url = "http://localhost:8000/api/threads/5/batch-translate"
    payload = {
        "chapter_ids": [672, 673, 674, 675, 676, 677, 678, 679, 680, 681, 682, 683, 684, 685, 686],
        "ai_extract": True,
        "target_lang": "English",
        "overwrite": True
    }
    print("Triggering batch translation via POST /api/threads/5/batch-translate...")
    resp = httpx.post(url, json=payload, timeout=10.0)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    
    # Wait and check progress
    for _ in range(5):
        time.sleep(3)
        status_resp = httpx.get("http://localhost:8000/api/threads/5/batch-status")
        print(f"Status: {status_resp.json()}")
except Exception as e:
    print(f"Failed: {e}")
