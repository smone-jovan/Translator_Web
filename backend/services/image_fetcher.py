"""
Fetch gambar (cover / ilustrasi) dengan eskalasi anti-Cloudflare bertingkat.

Tier 1: httpx (cepat, hop redirect divalidasi SSRF)
Tier 2: curl_cffi impersonate chrome (lolos fingerprint TLS/hotlink ringan)
Tier 3: browser stealth (Playwright/patchright via StealthyNovelAdapter) yang menyelesaikan
        challenge Cloudflare, lalu mengambil bytes gambar dari dalam halaman.

Eskalasi hanya terjadi bila tier sebelumnya terblokir (403/429/503, challenge HTML, atau
error transport). Miss definitif (404/410) langsung berhenti.
"""

import base64
from typing import NamedTuple, Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from services.security import (
    ResponseTooLarge,
    create_safe_async_client,
    egress_proxies,
    follow_redirects_safely,
    validate_external_url,
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
_BLOCK_STATUSES = frozenset({403, 429, 503})
_BROWSER_TIMEOUT_MS = 45000
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_FETCH_IN_PAGE_JS = """
async (maxBytes) => {
  const resp = await fetch(location.href, { credentials: 'include' });
  if (!resp.ok) return null;
  const buf = new Uint8Array(await resp.arrayBuffer());
  if (buf.length === 0 || buf.length > maxBytes) return null;
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < buf.length; i += chunk) {
    bin += String.fromCharCode.apply(null, buf.subarray(i, i + chunk));
  }
  return btoa(bin);
}
"""


class TierResult(NamedTuple):
    """data: bytes gambar bila sukses. escalate: True bila tier berikutnya layak dicoba."""

    data: Optional[bytes]
    escalate: bool


RASTER_IMAGE_EXTS = frozenset({"png", "jpeg", "gif", "webp", "avif", "bmp"})


def sniff_raster_ext(data: bytes) -> Optional[str]:
    """Ekstensi gambar raster dari magic bytes, atau None. SVG sengaja tidak dikenali (vektor aktif -> XSS)."""
    if not data:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return "avif"
    if data.startswith(b"BM"):
        return "bmp"
    return None


def is_image_bytes(data: bytes) -> bool:
    """Sniff magic bytes. Berbeda dari guess_image_ext_from_bytes, tidak default ke jpeg."""
    return sniff_raster_ext(data) is not None


def _ext_for(data: bytes) -> str:
    from services.image_cacher import guess_image_ext_from_bytes

    return guess_image_ext_from_bytes(data) or "jpeg"


def referer_for(url: str, override: Optional[str] = None) -> str:
    if override:
        return override
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def classify_response(status: int, content: bytes) -> TierResult:
    if status == 200 and content:
        if is_image_bytes(content):
            return TierResult(content, False)
        return TierResult(None, True)  # 200 tapi HTML (challenge / hotlink page)
    if status in _BLOCK_STATUSES:
        return TierResult(None, True)
    return TierResult(None, False)


def _headers(url: str, referer: Optional[str]) -> dict:
    return {
        "User-Agent": _USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": referer_for(url, referer),
    }


async def _fetch_httpx(url: str, referer: Optional[str]) -> TierResult:
    try:
        async with create_safe_async_client(
            follow_redirects=True,
            timeout=httpx.Timeout(12.0, connect=4.0),
            max_response_bytes=MAX_IMAGE_BYTES,
        ) as client:
            resp = await client.get(url, headers=_headers(url, referer))
        return classify_response(resp.status_code, resp.content)
    except HTTPException:
        raise
    except ResponseTooLarge:
        return TierResult(None, False)
    except httpx.HTTPError:
        return TierResult(None, True)


async def _fetch_curl(url: str, referer: Optional[str]) -> TierResult:
    try:
        from curl_cffi.requests import AsyncSession

        async with AsyncSession(
            impersonate="chrome120",
            headers=_headers(url, referer),
            timeout=20.0,
            allow_redirects=False,
            proxies=egress_proxies(),
        ) as session:
            resp, _ = await follow_redirects_safely(
                lambda u: session.get(u, allow_redirects=False), url
            )
        return classify_response(resp.status_code, resp.content)
    except HTTPException:
        raise
    except Exception:
        return TierResult(None, True)


async def _fetch_browser(url: str, workspace: Optional[str]) -> TierResult:
    captured: dict = {}

    def _grab(page) -> None:
        captured["b64"] = page.evaluate(_FETCH_IN_PAGE_JS, MAX_IMAGE_BYTES)

    try:
        from services.scrapers.stealth_base import StealthyNovelAdapter

        stealth = StealthyNovelAdapter(workspace=workspace, adaptive_domain=url)
        # strict_ssrf: URL dari pengguna/situs eksternal, jadi hanya jalur Playwright native
        # yang memvalidasi setiap request browser (ADR-126).
        await stealth.fetch_stealth_page(
            url,
            solve_cloudflare=True,
            disable_resources=False,
            page_action=_grab,
            timeout_ms=_BROWSER_TIMEOUT_MS,
            strict_ssrf=True,
        )
    except HTTPException:
        raise
    except Exception:
        return TierResult(None, False)

    b64 = captured.get("b64")
    if not b64:
        return TierResult(None, False)
    try:
        data = base64.b64decode(b64)
    except Exception:
        return TierResult(None, False)
    return TierResult(data if is_image_bytes(data) else None, False)


async def fetch_image_adaptive(
    url: str,
    *,
    referer: Optional[str] = None,
    workspace: Optional[str] = None,
    allow_browser: bool = True,
) -> Optional[tuple[bytes, str]]:
    """
    Ambil gambar dari URL eksternal. Mengembalikan (bytes, ext) atau None.
    HTTPException(400) dari validasi SSRF sengaja dilempar ulang.
    """
    validate_external_url(url)

    result = await _fetch_httpx(url, referer)
    if result.data is None and result.escalate:
        result = await _fetch_curl(url, referer)
    if result.data is None and result.escalate and allow_browser:
        result = await _fetch_browser(url, workspace)

    data = result.data
    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    return data, _ext_for(data)
