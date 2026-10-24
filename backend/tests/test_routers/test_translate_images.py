import json
from unittest.mock import patch

import pymupdf
import pytest
from fastapi.testclient import TestClient

from database import get_db
from main import app
from services.ai.base import BaseAIProviderAdapter

INDEX_MODEL = "index-translate-2b"


def make_image(width=600, height=900, fmt="png"):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height))
    pix.clear_with(150)
    return pix.tobytes(fmt)


class RecordingProvider(BaseAIProviderAdapter):
    def __init__(self, fail_on_call=None):
        self.calls = []
        self.max_tokens = []
        self.fail_on_call = fail_on_call

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
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


def _files(payloads):
    return [("files", (f"{i}.png", data, "image/png")) for i, data in enumerate(payloads)]


def _post(client, provider, payloads, model=INDEX_MODEL):
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
        return client.post(
            "/api/translate/images",
            files=_files(payloads),
            data={"model": model, "target_lang": "Indonesian"},
        )


def _events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def test_streams_one_page_event_per_image_in_upload_order(client):
    provider = RecordingProvider()
    resp = _post(client, provider, [make_image(), make_image(fmt="jpeg")])

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    events = _events(resp)
    assert [e["type"] for e in events] == ["start", "page", "page", "done"]
    assert events[0]["pages"] == 2
    assert [(e["index"], e["translation"], e["mode"]) for e in events[1:3]] == [
        (0, "terjemahan-1", "image"),
        (1, "terjemahan-2", "image"),
    ]
    assert events[-1] == {"type": "done", "model_used": INDEX_MODEL}


def test_each_image_uses_image_prompt_and_official_token_cap(client):
    provider = RecordingProvider()
    _post(client, provider, [make_image()])

    (messages,) = provider.calls
    parts = messages[0]["content"]
    assert parts[0]["text"].startswith("请将图片中的文本翻译为印尼语")
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert provider.max_tokens == [1024]


def test_bad_image_reports_page_error_and_continues(client):
    provider = RecordingProvider()
    resp = _post(client, provider, [b"not an image", make_image()])

    events = _events(resp)
    assert [e["type"] for e in events] == ["start", "page_error", "page", "done"]
    assert events[2]["translation"] == "terjemahan-1"


def test_provider_failure_does_not_leak_details(client):
    resp = _post(client, RecordingProvider(fail_on_call=1), [make_image(), make_image()])

    assert "secret-host" not in resp.text
    assert [e["type"] for e in _events(resp)] == ["start", "page_error", "page", "done"]


def test_rejects_non_index_model(client):
    provider = RecordingProvider()
    resp = _post(client, provider, [make_image()], model="gemma-3-4b")

    assert resp.status_code == 400
    assert provider.calls == []


def test_too_many_images_returns_413(client):
    provider = RecordingProvider()
    resp = _post(client, provider, [make_image(10, 10)] * 61)

    assert resp.status_code == 413
    assert provider.calls == []


def test_no_files_is_rejected(client):
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=RecordingProvider()):
        resp = client.post("/api/translate/images", data={"model": INDEX_MODEL})

    assert resp.status_code in (400, 422)


def test_export_pdf_returns_image_and_text_pages(client):
    resp = client.post(
        "/api/translate/images/export-pdf",
        files=_files([make_image(), make_image(fmt="jpeg")]),
        data={"translations": json.dumps(["Halo dunia.", "Sampai jumpa."])},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    doc = pymupdf.open(stream=resp.content, filetype="pdf")
    assert len(doc) == 4
    assert "Sampai jumpa." in doc[3].get_text()


@pytest.mark.parametrize(
    "translations",
    ["not json", json.dumps(["only one"]), json.dumps([1, 2]), json.dumps({"a": 1})],
)
def test_export_pdf_rejects_bad_translations(client, translations):
    resp = client.post(
        "/api/translate/images/export-pdf",
        files=_files([make_image(), make_image()]),
        data={"translations": translations},
    )

    assert resp.status_code == 400


def test_export_pdf_rejects_non_image(client):
    resp = client.post(
        "/api/translate/images/export-pdf",
        files=_files([b"<html></html>"]),
        data={"translations": json.dumps(["x"])},
    )

    assert resp.status_code == 400
