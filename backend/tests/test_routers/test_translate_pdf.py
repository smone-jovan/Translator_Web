import json
from unittest.mock import patch

import pymupdf
import pytest
from fastapi.testclient import TestClient

from database import get_db
from main import app
from services.ai.base import BaseAIProviderAdapter

INDEX_MODEL = "index-translate-2b"
LONG_TEXT = "这是一段足够长的中文文本，用来判断页面带有文字层。"


def make_pdf(pages):
    """pages: str (text layer) or None (image-only page)."""
    doc = pymupdf.open()
    for content in pages:
        page = doc.new_page(width=595, height=842)
        if content is None:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
            pix.set_rect(pix.irect, (200, 30, 30))
            page.insert_image(pymupdf.Rect(50, 50, 300, 300), pixmap=pix)
        else:
            page.insert_text((72, 72), content, fontname="china-s")
    return doc.tobytes()


class RecordingProvider(BaseAIProviderAdapter):
    def __init__(self, fail_on_call=None):
        self.calls = []
        self.temperatures = []
        self.max_tokens = []
        self.fail_on_call = fail_on_call

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        self.temperatures.append(temperature)
        self.max_tokens.append(max_tokens)
        if self.fail_on_call == len(self.calls):
            raise Exception("connection refused to http://secret-host")
        return f"terjemahan-{len(self.calls)}"

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        yield "x"


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _post(client, provider, data=None, model=INDEX_MODEL, **form):
    payload = data if data is not None else make_pdf([LONG_TEXT])
    form = {"model": model, "target_lang": "Indonesian", **form}
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
        return client.post(
            "/api/translate/pdf", files={"file": ("a.pdf", payload, "application/pdf")}, data=form
        )


def _events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def test_streams_start_page_done_events_in_order(client):
    provider = RecordingProvider()
    resp = _post(client, provider, make_pdf([LONG_TEXT, None]))

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    events = _events(resp)
    assert events[0] == {"type": "start", "pages": 2}
    assert [e["type"] for e in events] == ["start", "page", "page", "done"]
    assert events[1] | {"translation": ""} == {
        "type": "page", "index": 0, "mode": "text", "translation": "",
    }
    assert events[2]["index"] == 1 and events[2]["mode"] == "image"
    assert events[-1] == {"type": "done", "model_used": INDEX_MODEL}


def test_text_page_uses_text_prompt_and_image_page_uses_image_prompt(client):
    provider = RecordingProvider()
    _post(client, provider, make_pdf([LONG_TEXT, None]))

    text_call, image_call = provider.calls
    assert isinstance(text_call[0]["content"], str)
    assert text_call[0]["content"].startswith("请将以下文本翻译为印尼语")
    assert LONG_TEXT in text_call[0]["content"]
    parts = image_call[0]["content"]
    assert parts[0]["text"].startswith("请将图片中的文本翻译为印尼语")
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_image_pages_use_official_token_cap(client):
    provider = RecordingProvider()
    _post(client, provider, make_pdf([None]))

    assert provider.max_tokens == [1024]


def test_page_error_does_not_stop_remaining_pages_or_leak_details(client):
    provider = RecordingProvider(fail_on_call=1)
    resp = _post(client, provider, make_pdf([None, None]))

    events = _events(resp)
    assert [e["type"] for e in events] == ["start", "page_error", "page", "done"]
    assert "secret-host" not in resp.text
    assert events[2]["translation"] == "terjemahan-2"


def test_rejects_non_index_model_before_streaming(client):
    provider = RecordingProvider()
    resp = _post(client, provider, model="gemma-3-4b")

    assert resp.status_code == 400
    assert provider.calls == []


@pytest.mark.parametrize("payload", [b"<html></html>", b"%PDF-1.7 garbage"])
def test_rejects_invalid_pdf_with_400(client, payload):
    provider = RecordingProvider()
    resp = _post(client, provider, payload)

    assert resp.status_code == 400
    assert provider.calls == []


def test_too_many_pages_returns_413(client):
    provider = RecordingProvider()
    resp = _post(client, provider, make_pdf(["p"] * 51))

    assert resp.status_code == 413
    assert provider.calls == []


def test_oversized_upload_returns_413(client):
    provider = RecordingProvider()
    resp = _post(client, provider, b"%PDF-" + b"0" * (20 * 1024 * 1024))

    assert resp.status_code == 413
    assert provider.calls == []
