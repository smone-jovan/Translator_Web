import httpx

try:
    resp = httpx.get("http://localhost:8000/api/threads/active-batch")
    data = resp.json()
    print("ACTIVE BATCH STATUS:")
    print(f"Active: {data.get('active')}")
    print(f"Thread ID: {data.get('thread_id')}")
    print(f"Total: {data.get('total')}")
    print(f"Completed: {data.get('completed')}")
    current_title = data.get('current_chapter_title') or ""
    print(f"Current Chapter Title: {current_title.encode('ascii', 'replace').decode('ascii')}")
    print(f"Failed IDs: {data.get('failed_ids')}")
except Exception as e:
    print(f"Error querying status: {e}")
