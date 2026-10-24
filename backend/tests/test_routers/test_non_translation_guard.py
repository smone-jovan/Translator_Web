import base64
import json
from unittest.mock import patch

import pymupdf
import pytest
from fastapi.testclient import TestClient

from database import get_db
from main import app
from services.ai.base import BaseAIProviderAdapter, Completion
from services.manga_detector import DetectedBox, TEXT_BUBBLE

INDEX_MODEL = "index-translate-2b"
REFUSAL = "This image contains explicit adult content, which may not be appropriate for all audiences."
DESCRIPTION = (
    "This is an anime-style illustration of a female character in a bedroom. "
    "The background shows a window and the panel has a soft style."
)
LOOP = "Look at her now!!\nShe's awake!!\n" * 10
PNG_URL = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


def make_image(width=600, height=900):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height))
    pix.clear_with(150)
    return pix.tobytes("png")


class ScriptedProvider(BaseAIProviderAdapter):
    """Plays back (text, finish_reason) replies in order; records the extra sampling parameters."""

    def __init__(self, *replies, reject_extra=False):
        self.replies = list(replies)
        self.extras = []
        self.calls = 0
        self.reject_extra = reject_extra

    async def chat_completion_detailed(self, messages, temperature=0.3, max_tokens=None, extra=None):
        self.extras.append(extra)
        if self.reject_extra and extra:
            raise Exception("HTTP 400: unknown parameter")
        self.calls += 1
        text, finish = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        return Completion(text, finish)

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        return (await self.chat_completion_detailed(messages, temperature, max_tokens)).text

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        yield ""


class PlainProvider(BaseAIProviderAdapter):
    """An old-style provider that only has chat_completion."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls += 1
        return self.reply

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        yield ""


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def post_images(client, provider, count=1, **form):
    files = [("files", (f"{i}.png", make_image(), "image/png")) for i in range(count)]
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
        return client.post("/api/translate/images", files=files, data={"model": INDEX_MODEL, **form})


def events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def pages(resp):
    return [e for e in events(resp) if e["type"] in ("page", "page_error")]


class TestRefusalAndDescription:
    @pytest.mark.parametrize("text,reason", [(REFUSAL, "refusal"), (DESCRIPTION, "description")])
    def test_becomes_a_labelled_page_error_without_retry(self, client, text, reason):
        provider = ScriptedProvider((text, "stop"))

        (page,) = pages(post_images(client, provider))

        assert page["type"] == "page_error" and page["reason"] == reason
        assert page["error"] and "gambar" in page["error"].lower()
        assert provider.calls == 1

    def test_other_pages_still_succeed(self, client):
        provider = ScriptedProvider((REFUSAL, "stop"), ("Halo dunia.", "stop"))

        first, second = pages(post_images(client, provider, count=2))

        assert first["type"] == "page_error" and second["type"] == "page"
        assert second["translation"] == "Halo dunia."

    def test_a_real_translation_is_unaffected(self, client):
        (page,) = pages(post_images(client, ScriptedProvider(("Awas, bahaya di depan.", "stop"))))

        assert page["type"] == "page" and page["translation"] == "Awas, bahaya di depan."
        assert "truncated" not in page


class TestLoopRetry:
    def test_loop_is_retried_once_with_a_stronger_penalty_and_can_succeed(self, client):
        provider = ScriptedProvider((LOOP, "length"), ("Dia sudah bangun.", "stop"))

        (page,) = pages(post_images(client, provider))

        assert page["type"] == "page" and page["translation"] == "Dia sudah bangun."
        first, second = provider.extras
        assert first["repeat_penalty"] < second["repeat_penalty"]

    def test_two_loops_in_a_row_become_a_loop_error(self, client):
        provider = ScriptedProvider((LOOP, "length"))

        (page,) = pages(post_images(client, provider))

        assert page["type"] == "page_error" and page["reason"] == "loop"
        assert provider.calls == 2


class TestTruncation:
    def test_clean_but_cut_reply_is_kept_and_flagged(self, client):
        provider = ScriptedProvider(("Kalimat yang sah tetapi terpotong di", "length"))

        (page,) = pages(post_images(client, provider))

        assert page["type"] == "page" and page["truncated"] is True


class TestPenaltyParameter:
    def test_image_requests_send_the_repeat_penalty(self, client):
        provider = ScriptedProvider(("Halo.", "stop"))

        post_images(client, provider)

        assert provider.extras == [{"repeat_penalty": pytest.approx(1.1)}]

    def test_server_rejecting_the_parameter_falls_back_to_a_plain_request(self, client):
        provider = ScriptedProvider(("Halo.", "stop"), reject_extra=True)

        (page,) = pages(post_images(client, provider))

        assert page["type"] == "page" and page["translation"] == "Halo."

    def test_old_style_providers_without_detailed_completion_still_work(self, client):
        provider = PlainProvider("Halo dari provider lama.")

        (page,) = pages(post_images(client, provider))

        assert page["type"] == "page" and page["translation"] == "Halo dari provider lama."

    def test_old_style_provider_refusals_are_still_caught(self, client):
        (page,) = pages(post_images(client, PlainProvider(REFUSAL)))

        assert page["type"] == "page_error" and page["reason"] == "refusal"


class TestOverlayCrops:
    def test_a_refused_crop_is_skipped_and_the_rest_are_kept(self, client):
        provider = ScriptedProvider(("Halo.", "stop"), (REFUSAL, "stop"), ("Sampai jumpa.", "stop"))
        detected = [DetectedBox(10, 10, 100, 60, TEXT_BUBBLE, 0.9), DetectedBox(120, 10, 200, 60, TEXT_BUBBLE, 0.9),
                    DetectedBox(220, 10, 300, 60, TEXT_BUBBLE, 0.9)]

        with patch("routers.image_batch_translate.detect_text_boxes", lambda _b: detected), patch(
            "routers.image_batch_translate.load_detector", lambda: None
        ):
            resp = post_images(client, provider, overlay="true")

        (page,) = pages(resp)
        assert page["mode"] == "overlay"
        assert [b["text"] for b in page["boxes"]] == ["Halo.", "Sampai jumpa."]


class TestSingleImageEndpoint:
    def _post(self, client, provider):
        with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
            return client.post(
                "/api/translate/image", json={"image_data_url": PNG_URL, "model": INDEX_MODEL, "target_lang": "Indonesian"}
            )

    def test_refusal_returns_422_with_a_clear_message(self, client):
        resp = self._post(client, ScriptedProvider((REFUSAL, "stop")))

        assert resp.status_code == 422
        assert "menolak" in resp.json()["detail"].lower()

    def test_normal_translation_still_returns_200(self, client):
        resp = self._post(client, ScriptedProvider(("Halo dunia.", "stop")))

        assert resp.status_code == 200 and resp.json()["translation"] == "Halo dunia."


class TestPdfImagePages:
    def test_refused_scanned_page_reports_the_reason(self, client):
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
        pix.clear_with(120)
        page.insert_image(pymupdf.Rect(50, 50, 300, 300), pixmap=pix)

        with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=ScriptedProvider((REFUSAL, "stop"))):
            resp = client.post(
                "/api/translate/pdf",
                files={"file": ("a.pdf", doc.tobytes(), "application/pdf")},
                data={"model": INDEX_MODEL},
            )

        error = [e for e in events(resp) if e["type"] == "page_error"]
        assert len(error) == 1 and error[0]["reason"] == "refusal"
