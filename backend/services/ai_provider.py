import httpx
import json
from typing import AsyncGenerator, List, Dict, Any

class AIProvider:
    """
    Handles robust connectivity to local LLM APIs with fallback mechanisms.
    """
    
    def __init__(self, base_url: str):
        self.primary_url = base_url.rstrip("/")
        if "/v1" not in self.primary_url:
            self.primary_url += "/v1"
            
        self.urls_to_try = [self.primary_url]
        if "localhost" in self.primary_url:
            self.urls_to_try.append(self.primary_url.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in self.primary_url:
            self.urls_to_try.append(self.primary_url.replace("127.0.0.1", "localhost"))

    async def stream_chat(self, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream chat completions with dual-stack fallback."""
        last_error = ""
        success = False
        
        for url in self.urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", f"{url}/chat/completions", json=payload) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            last_error = f"HTTP {response.status_code}: {error_text.decode()}"
                            continue
                        
                        success = True
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                if "[DONE]" in line:
                                    break
                                try:
                                    data = json.loads(line[6:])
                                    content = data["choices"][0]["delta"].get("content", "")
                                    if content:
                                        yield content
                                except:
                                    continue
                        return # Success, exit
            except Exception as e:
                last_error = str(e)
                continue
                
        if not success:
            raise Exception(f"Connection failed. Tried {', '.join(self.urls_to_try)}. Error: {last_error}")

    async def chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Non-streaming chat completion with dual-stack fallback."""
        last_error = ""
        for url in self.urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(f"{url}/chat/completions", json=payload)
                    if resp.status_code == 200:
                        return resp.json()
                    last_error = f"HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                last_error = str(e)
                continue
        
        raise Exception(f"Connection failed to LM Studio. Error: {last_error}")
    
    @staticmethod
    async def generate_batch(system_prompt: str, user_prompt: str, base_url: str = "http://localhost:1234") -> str:
        """Convenience method for one-off batch generations."""
        provider = AIProvider(base_url)
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "stream": False
        }
        res = await provider.chat_completion(payload)
        return res["choices"][0]["message"]["content"]
