"""
SSRF protection utilities.

Validates external URLs before making outbound HTTP requests to prevent
access to internal network resources, cloud metadata endpoints, and
loopback addresses.
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
import httpx


def validate_external_url(url: str) -> None:
    """
    Validate that a URL points to a genuinely external host.

    Raises HTTPException(400) if the URL:
    - Uses a non-HTTP(S) scheme
    - Contains embedded credentials
    - Resolves to a loopback, private, link-local, multicast, reserved, or non-global IP
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    # Enforce HTTP(S) only
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail=f"URL scheme '{parsed.scheme}' is not allowed; use http or https",
        )

    # Reject embedded credentials
    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=400,
            detail="URLs with embedded credentials are not allowed",
        )

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="URL has no hostname")

    _resolve_checked(hostname, None)


_FORBIDDEN_DETAIL = "Access to private or local network resources is forbidden"


def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        not ip.is_global
        or ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
    )


def _resolve_checked(hostname: str, port: int | None) -> list[str]:
    """Resolve `hostname`; tolak bila SALAH SATU alamatnya non-publik. Kembalikan daftar IP."""
    try:
        addr_infos = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, ValueError):
        # UnicodeError: label IDNA > 63 karakter / label kosong ("a..b").
        raise HTTPException(status_code=400, detail=f"Cannot resolve hostname: {hostname}")

    ips: list[str] = []
    for family, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            # Alamat yang tidak bisa diklasifikasi diperlakukan sebagai terlarang.
            raise HTTPException(status_code=400, detail=_FORBIDDEN_DETAIL)
        if _is_forbidden_ip(ip):
            raise HTTPException(status_code=400, detail=_FORBIDDEN_DETAIL)
        ips.append(ip_str)
    if not ips:
        raise HTTPException(status_code=400, detail=f"Cannot resolve hostname: {hostname}")
    return ips


def resolve_public_ip(hostname: str, port: int) -> str:
    """
    Resolve `hostname` dan kembalikan satu IP publik yang SUDAH divalidasi.

    Pemanggil harus menyambung ke IP ini (bukan ke nama host) agar tidak ada celah
    validasi-lalu-resolve-ulang (DNS rebinding). HTTPException(400) bila non-publik.
    """
    host = (hostname or "").strip().rstrip(".") if hostname else ""
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if not host:
        raise HTTPException(status_code=400, detail="URL has no hostname")
    return _resolve_checked(host, port)[0]


async def validate_redirect_response(response: httpx.Response) -> None:
    """
    httpx response hook to validate redirect target URLs against SSRF before following.
    """
    if response.is_redirect and "location" in response.headers:
        redirect_url = str(response.url.join(response.headers["location"]))
        validate_external_url(redirect_url)


_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class TooManyRedirects(Exception):
    """Rantai redirect melebihi batas `max_redirects`."""


def _location_header(response: Any) -> str | None:
    headers = getattr(response, "headers", None) or {}
    try:
        return headers.get("location") or headers.get("Location")
    except Exception:
        return None


async def follow_redirects_safely(
    get: Callable[[str], Awaitable[Any]],
    url: str,
    *,
    max_redirects: int = 5,
) -> tuple[Any, str]:
    """
    Ikuti redirect secara manual dan validasi SSRF setiap hop SEBELUM hop itu diminta.

    `get(url)` harus melakukan satu request TANPA mengikuti redirect (mis. curl_cffi dengan
    `allow_redirects=False`). Mengembalikan `(response_akhir, url_akhir)`.
    Melempar HTTPException(400) bila ada hop ke jaringan privat, atau TooManyRedirects.
    """
    validate_external_url(url)
    current = url
    redirects = 0
    while True:
        response = await get(current)
        location = _location_header(response)
        if getattr(response, "status_code", None) in _REDIRECT_STATUSES and location:
            if redirects >= max_redirects:
                raise TooManyRedirects(f"More than {max_redirects} redirects starting at {url}")
            next_url = urljoin(current, location.strip())
            validate_external_url(next_url)
            redirects += 1
            current = next_url
            continue
        return response, current


def egress_proxy_url() -> str:
    """URL proxy egress lokal yang me-resolve dan mem-pin IP publik saat connect (anti DNS-rebinding, A-18)."""
    from services.egress_proxy import get_egress_proxy

    return get_egress_proxy().server_url


def egress_proxies() -> dict[str, str]:
    """Argumen `proxies=` untuk curl_cffi."""
    url = egress_proxy_url()
    return {"http": url, "https": url}


def create_safe_async_client(**kwargs: Any) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient configured to prevent SSRF bypass via HTTP 30x redirects.
    `max_response_bytes` (opsional) membatasi ukuran body respons.
    """
    max_response_bytes = kwargs.pop("max_response_bytes", None)
    if not any(k in kwargs for k in ("transport", "mounts", "proxy")):
        # Koneksi keluar lewat proxy yang memvalidasi IP tujuan saat connect (bukan hanya saat pra-validasi).
        kwargs["proxy"] = egress_proxy_url()
    kwargs.setdefault("follow_redirects", True)
    event_hooks = dict(kwargs.pop("event_hooks", None) or {})
    res_hooks = list(event_hooks.get("response", []))
    if validate_redirect_response not in res_hooks:
        res_hooks.append(validate_redirect_response)
    event_hooks["response"] = res_hooks
    client = httpx.AsyncClient(event_hooks=event_hooks, **kwargs)
    if max_response_bytes:
        cap_response_size(client, max_response_bytes)
    return client



# --- Batas ukuran (A-31): hentikan unduh/upload sebelum seluruh body masuk memori ---

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_HTML_BYTES = 10 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 200
_UPLOAD_CHUNK_BYTES = 1024 * 1024


class ResponseTooLarge(Exception):
    """Body respons melebihi batas byte yang diizinkan."""


class _CappedStream(httpx.AsyncByteStream):
    """Bungkus stream respons; lempar ResponseTooLarge begitu total byte melewati batas."""

    def __init__(self, inner: Any, max_bytes: int) -> None:
        self._inner = inner
        self._max = max_bytes

    async def __aiter__(self):
        total = 0
        async for chunk in self._inner:
            total += len(chunk)
            if total > self._max:
                raise ResponseTooLarge(f"body > {self._max} bytes")
            yield chunk

    async def aclose(self) -> None:
        await self._inner.aclose()


def cap_response_size(client: httpx.AsyncClient, max_bytes: int) -> httpx.AsyncClient:
    """Pasang hook respons yang membatasi ukuran body (Content-Length + stream) sebelum dibaca ke memori."""

    async def _hook(response: httpx.Response) -> None:
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise ResponseTooLarge(f"Content-Length {declared} > {max_bytes}")
        response.stream = _CappedStream(response.stream, max_bytes)

    client.event_hooks["response"] = [*client.event_hooks.get("response", []), _hook]
    return client


async def read_upload_limited(file: Any, *, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Baca UploadFile bertahap; 413 bila melewati max_bytes."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="File terlalu besar")
        chunks.append(chunk)
    return b"".join(chunks)


def check_zip_safe(
    content: bytes,
    *,
    max_total: int = MAX_ZIP_UNCOMPRESSED_BYTES,
    max_ratio: int = MAX_ZIP_COMPRESSION_RATIO,
) -> None:
    """Tolak zip bomb: total ukuran terdekompresi dan rasio kompresi dicek dari direktori zip."""
    import io
    import zipfile

    try:
        infos = zipfile.ZipFile(io.BytesIO(content)).infolist()
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Arsip tidak valid")
    total = sum(i.file_size for i in infos)
    if total > max_total:
        raise HTTPException(status_code=413, detail="Isi arsip terlalu besar setelah dekompresi")
    if any(i.compress_size and i.file_size / i.compress_size > max_ratio for i in infos):
        raise HTTPException(status_code=413, detail="Rasio kompresi arsip mencurigakan")
