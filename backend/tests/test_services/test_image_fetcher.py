"""
Fetch gambar (cover/ilustrasi) dengan eskalasi anti-Cloudflare:
httpx -> curl_cffi (impersonate) -> browser stealth.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from services import image_fetcher as imf

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
CF_HTML = b"<html><title>Just a moment...</title>cf-browser-verification</html>"


class _Resp:
    def __init__(self, status_code=200, content=b"", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


def test_is_image_bytes_accepts_known_formats_and_rejects_html():
    assert imf.is_image_bytes(PNG)
    assert imf.is_image_bytes(b"\xff\xd8\xff\xe0JFIF")
    assert imf.is_image_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8X")
    assert imf.is_image_bytes(b"GIF89a\x01\x00")
    assert not imf.is_image_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")  # A-04: SVG ditolak
    assert not imf.is_image_bytes(CF_HTML)
    assert not imf.is_image_bytes(b"")


def test_referer_for_uses_target_origin_unless_overridden():
    assert imf.referer_for("https://cdn.site.org/a/b.png") == "https://cdn.site.org/"
    assert imf.referer_for("https://cdn.site.org/a.png", "https://x.org/") == "https://x.org/"


@pytest.mark.asyncio
async def test_tier1_success_does_not_escalate(monkeypatch):
    monkeypatch.setattr(imf, "validate_external_url", lambda u: None)
    t1 = AsyncMock(return_value=imf.TierResult(PNG, False))
    t2 = AsyncMock()
    t3 = AsyncMock()
    monkeypatch.setattr(imf, "_fetch_httpx", t1)
    monkeypatch.setattr(imf, "_fetch_curl", t2)
    monkeypatch.setattr(imf, "_fetch_browser", t3)

    result = await imf.fetch_image_adaptive("https://cdn.site.org/c.png")

    assert result == (PNG, "png")
    t2.assert_not_called()
    t3.assert_not_called()


@pytest.mark.asyncio
async def test_escalates_to_curl_when_tier1_blocked(monkeypatch):
    monkeypatch.setattr(imf, "validate_external_url", lambda u: None)
    monkeypatch.setattr(imf, "_fetch_httpx", AsyncMock(return_value=imf.TierResult(None, True)))
    t2 = AsyncMock(return_value=imf.TierResult(PNG, False))
    t3 = AsyncMock()
    monkeypatch.setattr(imf, "_fetch_curl", t2)
    monkeypatch.setattr(imf, "_fetch_browser", t3)

    result = await imf.fetch_image_adaptive("https://cdn.site.org/c.png")

    assert result == (PNG, "png")
    t2.assert_awaited_once()
    t3.assert_not_called()


@pytest.mark.asyncio
async def test_escalates_to_browser_when_curl_also_blocked(monkeypatch):
    monkeypatch.setattr(imf, "validate_external_url", lambda u: None)
    monkeypatch.setattr(imf, "_fetch_httpx", AsyncMock(return_value=imf.TierResult(None, True)))
    monkeypatch.setattr(imf, "_fetch_curl", AsyncMock(return_value=imf.TierResult(None, True)))
    t3 = AsyncMock(return_value=imf.TierResult(PNG, False))
    monkeypatch.setattr(imf, "_fetch_browser", t3)

    result = await imf.fetch_image_adaptive("https://cdn.site.org/c.png")

    assert result == (PNG, "png")
    t3.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_tier_skipped_when_disallowed(monkeypatch):
    monkeypatch.setattr(imf, "validate_external_url", lambda u: None)
    monkeypatch.setattr(imf, "_fetch_httpx", AsyncMock(return_value=imf.TierResult(None, True)))
    monkeypatch.setattr(imf, "_fetch_curl", AsyncMock(return_value=imf.TierResult(None, True)))
    t3 = AsyncMock()
    monkeypatch.setattr(imf, "_fetch_browser", t3)

    result = await imf.fetch_image_adaptive("https://cdn.site.org/c.png", allow_browser=False)

    assert result is None
    t3.assert_not_called()


@pytest.mark.asyncio
async def test_definitive_miss_does_not_escalate(monkeypatch):
    monkeypatch.setattr(imf, "validate_external_url", lambda u: None)
    monkeypatch.setattr(imf, "_fetch_httpx", AsyncMock(return_value=imf.TierResult(None, False)))
    t2 = AsyncMock()
    t3 = AsyncMock()
    monkeypatch.setattr(imf, "_fetch_curl", t2)
    monkeypatch.setattr(imf, "_fetch_browser", t3)

    assert await imf.fetch_image_adaptive("https://cdn.site.org/gone.png") is None
    t2.assert_not_called()
    t3.assert_not_called()


@pytest.mark.asyncio
async def test_ssrf_violation_propagates(monkeypatch):
    def boom(url):
        raise HTTPException(status_code=400, detail="blocked")

    monkeypatch.setattr(imf, "validate_external_url", boom)
    with pytest.raises(HTTPException):
        await imf.fetch_image_adaptive("http://127.0.0.1/x.png")


@pytest.mark.asyncio
async def test_oversized_payload_is_rejected(monkeypatch):
    monkeypatch.setattr(imf, "validate_external_url", lambda u: None)
    huge = PNG + b"\x00" * (imf.MAX_IMAGE_BYTES + 1)
    monkeypatch.setattr(imf, "_fetch_httpx", AsyncMock(return_value=imf.TierResult(huge, False)))

    assert await imf.fetch_image_adaptive("https://cdn.site.org/huge.png") is None


def test_classify_response_flags_challenge_and_block_statuses():
    ok = imf.classify_response(200, PNG)
    assert ok == imf.TierResult(PNG, False)
    # 200 tapi HTML challenge -> eskalasi
    assert imf.classify_response(200, CF_HTML) == imf.TierResult(None, True)
    # status pemblokiran -> eskalasi
    for status in (403, 429, 503):
        assert imf.classify_response(status, b"") == imf.TierResult(None, True)
    # miss definitif -> berhenti
    for status in (404, 410, 400):
        assert imf.classify_response(status, b"") == imf.TierResult(None, False)
