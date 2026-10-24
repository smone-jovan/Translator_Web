import json
from unittest.mock import patch

import pymupdf
import pytest
from fastapi.testclient import TestClient

from database import get_db
from main import app
from services.ai.base import BaseAIProviderAdapter
from services.image_zip import MAX_IMAGES

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
    resp = _post(client, provider, [make_image(10, 10)] * (MAX_IMAGES + 1))

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


# ---- overlay mode -----------------------------------------------------------------------------

from services.manga_detector import DetectedBox, DetectorUnavailableError, TEXT_BUBBLE  # noqa: E402


def _detector(*rects):
    return lambda _bytes: [DetectedBox(x0, y0, x1, y1, TEXT_BUBBLE, 0.9) for x0, y0, x1, y1 in rects]


def _post_overlay(client, provider, payloads, detector, available=True):
    def fake_load():
        if not available:
            raise DetectorUnavailableError("missing")

    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider), patch(
        "routers.image_batch_translate.detect_text_boxes", detector
    ), patch("routers.image_batch_translate.load_detector", fake_load):
        return client.post(
            "/api/translate/images",
            files=_files(payloads),
            data={"model": INDEX_MODEL, "target_lang": "Indonesian", "overlay": "true"},
        )


def test_overlay_translates_each_box_and_returns_boxes(client):
    provider = RecordingProvider()
    resp = _post_overlay(client, provider, [make_image()], _detector((300, 20, 400, 100), (20, 20, 120, 100)))

    events = _events(resp)
    assert [e["type"] for e in events] == ["start", "page", "done"]
    page = events[1]
    assert page["mode"] == "overlay"
    assert page["boxes"] == [
        {"x0": 300, "y0": 20, "x1": 400, "y1": 100, "text": "terjemahan-1"},
        {"x0": 20, "y0": 20, "x1": 120, "y1": 100, "text": "terjemahan-2"},
    ]
    assert page["translation"] == "terjemahan-1\n\nterjemahan-2"
    assert len(provider.calls) == 2


def test_overlay_without_detected_boxes_falls_back_to_whole_image(client):
    provider = RecordingProvider()
    resp = _post_overlay(client, provider, [make_image()], _detector())

    page = _events(resp)[1]
    assert page["mode"] == "image" and "boxes" not in page
    assert len(provider.calls) == 1


def test_overlay_with_missing_model_is_rejected_before_streaming(client):
    provider = RecordingProvider()
    resp = _post_overlay(client, provider, [make_image()], _detector(), available=False)

    assert resp.status_code == 400
    assert provider.calls == []


def test_overlay_provider_down_reports_page_error_without_leaking(client):
    class Down(RecordingProvider):
        async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
            raise Exception("connection refused to http://secret-host")

    rects = [(i * 60, 10, i * 60 + 50, 60) for i in range(5)]
    resp = _post_overlay(client, Down(), [make_image(600, 300)], _detector(*rects))

    assert [e["type"] for e in _events(resp)] == ["start", "page_error", "done"]
    assert "secret-host" not in resp.text


def test_overlay_flag_is_off_by_default(client):
    provider = RecordingProvider()
    with patch("routers.image_batch_translate.detect_text_boxes") as detector:
        _post(client, provider, [make_image()])

    detector.assert_not_called()


# ---- export with boxes ------------------------------------------------------------------------

def _export(client, payloads, translations, **data):
    return client.post(
        "/api/translate/images/export-pdf",
        files=_files(payloads),
        data={"translations": json.dumps(translations), **data},
    )


def test_export_with_boxes_and_without_text_pages(client):
    boxes = [[{"x0": 50, "y0": 50, "x1": 300, "y1": 200, "text": "Halo"}], []]
    resp = _export(
        client,
        [make_image(), make_image()],
        ["a", "b"],
        boxes=json.dumps(boxes),
        include_text_pages="false",
    )

    assert resp.status_code == 200
    assert len(pymupdf.open(stream=resp.content, filetype="pdf")) == 2


def test_export_with_boxes_keeps_text_pages_by_default(client):
    boxes = [[{"x0": 50, "y0": 50, "x1": 300, "y1": 200, "text": "Halo"}]]
    resp = _export(client, [make_image()], ["a"], boxes=json.dumps(boxes))

    assert len(pymupdf.open(stream=resp.content, filetype="pdf")) == 2


@pytest.mark.parametrize(
    "boxes",
    [
        "not json",
        json.dumps({"a": 1}),
        json.dumps([[], []]),  # wrong page count
        json.dumps([[{"x0": "1", "y0": 0, "x1": 10, "y1": 10, "text": "x"}]]),
        json.dumps([[{"x0": 0, "y0": 0, "x1": 10, "y1": 10}]]),  # no text
        json.dumps([[{"x0": 0, "y0": 0, "x1": 10, "y1": 10, "text": 5}]]),
        json.dumps([[{"x0": 0, "y0": 0, "x1": 10, "y1": 10, "text": "x" * 2001}]]),
        json.dumps([[{"x0": 0, "y0": 0, "x1": 10, "y1": 10, "text": "x"}] * 101]),
        json.dumps([[{"x0": 0, "y0": 0, "x1": 10**9, "y1": 10, "text": "x"}]]),
    ],
)
def test_export_rejects_bad_boxes(client, boxes):
    resp = _export(client, [make_image()], ["a"], boxes=boxes)

    assert resp.status_code == 400


# ---- ZIP uploads ------------------------------------------------------------------------------

import io  # noqa: E402
import zipfile  # noqa: E402


def make_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buffer.getvalue()


def _zip_files(data, name="chapter.zip"):
    return [("files", (name, data, "application/zip"))]


def _post_zip(client, provider, data, **form):
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
        return client.post(
            "/api/translate/images",
            files=_zip_files(data),
            data={"model": INDEX_MODEL, "target_lang": "Indonesian", **form},
        )


def test_zip_upload_is_expanded_in_natural_order_with_names(client):
    provider = RecordingProvider()
    archive = make_zip([("ch/p10.png", make_image()), ("ch/p2.png", make_image(fmt="png")), ("ch/readme.txt", b"x")])

    resp = _post_zip(client, provider, archive)

    events = _events(resp)
    assert events[0] == {"type": "start", "pages": 2, "names": ["p2.png", "p10.png"]}
    assert [e["type"] for e in events] == ["start", "page", "page", "done"]
    assert len(provider.calls) == 2


def test_plain_uploads_also_report_their_names(client):
    resp = _post(client, RecordingProvider(), [make_image()])

    assert _events(resp)[0]["names"] == ["0.png"]


def test_zip_with_bad_member_reports_page_error_and_continues(client):
    archive = make_zip([("a.png", b"not really a png"), ("b.png", make_image())])

    resp = _post_zip(client, RecordingProvider(), archive)

    assert [e["type"] for e in _events(resp)] == ["start", "page_error", "page", "done"]


@pytest.mark.parametrize(
    "archive",
    [b"PK\x03\x04 corrupt", make_zip([("readme.txt", b"x")]), make_zip([])],
)
def test_unusable_zip_returns_400_without_calling_the_model(client, archive):
    provider = RecordingProvider()

    resp = _post_zip(client, provider, archive)

    assert resp.status_code == 400
    assert provider.calls == []


def test_zip_with_too_many_images_returns_413(client):
    archive = make_zip([(f"{i}.png", make_image(10, 10)) for i in range(MAX_IMAGES + 1)])

    resp = _post_zip(client, RecordingProvider(), archive)

    assert resp.status_code == 413


def test_zip_mixed_with_other_files_is_rejected(client):
    provider = RecordingProvider()
    files = _zip_files(make_zip([("a.png", make_image())])) + _files([make_image()])
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
        resp = client.post("/api/translate/images", files=files, data={"model": INDEX_MODEL})

    assert resp.status_code == 400
    assert provider.calls == []


def test_two_zips_are_rejected(client):
    files = _zip_files(make_zip([("a.png", make_image())])) * 2
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=RecordingProvider()):
        resp = client.post("/api/translate/images", files=files, data={"model": INDEX_MODEL})

    assert resp.status_code == 400


def test_export_pdf_accepts_a_zip(client):
    archive = make_zip([("p2.png", make_image()), ("p1.png", make_image())])

    resp = client.post(
        "/api/translate/images/export-pdf",
        files=_zip_files(archive),
        data={"translations": json.dumps(["satu", "dua"])},
    )

    assert resp.status_code == 200
    doc = pymupdf.open(stream=resp.content, filetype="pdf")
    assert len(doc) == 4
    assert "satu" in doc[1].get_text() and "dua" in doc[3].get_text()


def test_export_pdf_zip_translation_count_must_match_extracted_images(client):
    archive = make_zip([("a.png", make_image()), ("b.png", make_image())])

    resp = client.post(
        "/api/translate/images/export-pdf",
        files=_zip_files(archive),
        data={"translations": json.dumps(["only one"])},
    )

    assert resp.status_code == 400


def test_zip_accepts_a_long_webtoon_chapter(client):
    """Webtoon chapters are often 100+ slices: a ZIP above the old 60-image limit must still work."""
    count = 120
    provider = RecordingProvider()
    archive = make_zip([(f"{i:03d}.png", make_image(10, 10)) for i in range(count)])

    resp = _post_zip(client, provider, archive)

    events = _events(resp)
    assert events[0]["pages"] == count
    assert len(provider.calls) == count


def test_image_limit_is_at_least_200():
    assert MAX_IMAGES >= 200
