import base64

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from database import get_db
from main import app
from services.ai.base import BaseAIProviderAdapter

PNG_URL = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
INDEX_MODEL = "index-translate-2b"


class RecordingProvider(BaseAIProviderAdapter):
    def __init__(self, reply="Ada bahaya di depan, jangan mendekat."):
        self.calls = []
        self.reply = reply
        self.temperatures = []
        self.max_tokens = []

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        self.temperatures.append(temperature)
        self.max_tokens.append(max_tokens)
        return self.reply

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        yield self.reply


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _post(client, provider, **overrides):
    body = {"image_data_url": PNG_URL, "target_lang": "Indonesian", "model": INDEX_MODEL}
    body.update(overrides)
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
        return client.post("/api/translate/image", json=body)


def test_translates_image_with_index_translate_model(client):
    provider = RecordingProvider()
    resp = _post(client, provider)

    assert resp.status_code == 200
    assert resp.json() == {"translation": "Ada bahaya di depan, jangan mendekat.", "model_used": INDEX_MODEL}
    (messages,) = provider.calls
    assert messages[0]["content"][1] == {"type": "image_url", "image_url": {"url": PNG_URL}}
    assert messages[0]["content"][0]["text"].startswith("请将图片中的文本翻译为印尼语")


def test_strips_thinking_blocks_from_reply(client):
    provider = RecordingProvider(reply="<think>hmm</think>\n\nHalo dunia.")
    resp = _post(client, provider)

    assert resp.status_code == 200
    assert resp.json()["translation"] == "Halo dunia."


def test_rejects_non_index_model(client):
    provider = RecordingProvider()
    resp = _post(client, provider, model="gemma-3-4b")

    assert resp.status_code == 400
    assert provider.calls == []


@pytest.mark.parametrize("bad", ["https://example.com/a.png", "data:text/html;base64,PGh0bWw+", ""])
def test_rejects_invalid_image(client, bad):
    provider = RecordingProvider()
    resp = _post(client, provider, image_data_url=bad)

    assert resp.status_code == 400
    assert provider.calls == []


def test_oversized_image_returns_413(client):
    big = "data:image/png;base64," + base64.b64encode(b"x" * (10 * 1024 * 1024 + 1)).decode()
    provider = RecordingProvider()
    resp = _post(client, provider, image_data_url=big)

    assert resp.status_code == 413
    assert provider.calls == []


def test_provider_failure_returns_502_without_leaking_details(client):
    class Boom(RecordingProvider):
        async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
            raise Exception("connection refused to http://secret-host")

    resp = _post(client, Boom())

    assert resp.status_code == 502
    assert "secret-host" not in resp.text
