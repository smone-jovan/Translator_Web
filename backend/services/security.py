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


def create_safe_async_client(**kwargs: Any) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient configured to prevent SSRF bypass via HTTP 30x redirects.
    """
    kwargs.setdefault("follow_redirects", True)
    event_hooks = dict(kwargs.pop("event_hooks", None) or {})
    res_hooks = list(event_hooks.get("response", []))
    if validate_redirect_response not in res_hooks:
        res_hooks.append(validate_redirect_response)
    event_hooks["response"] = res_hooks
    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)

