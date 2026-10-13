"""
SSRF protection utilities.

Validates external URLs before making outbound HTTP requests to prevent
access to internal network resources, cloud metadata endpoints, and
loopback addresses.
"""

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Any

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

    # Resolve hostname and validate every resulting IP
    try:
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Cannot resolve hostname: {hostname}")

    for family, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if not ip.is_global or ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise HTTPException(
                status_code=400,
                detail="Access to private or local network resources is forbidden",
            )


async def validate_redirect_response(response: httpx.Response) -> None:
    """
    httpx response hook to validate redirect target URLs against SSRF before following.
    """
    if response.is_redirect and "location" in response.headers:
        redirect_url = str(response.url.join(response.headers["location"]))
        validate_external_url(redirect_url)


def create_safe_async_client(**kwargs: Any) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient configured to prevent SSRF bypass via HTTP 30x redirects.
    """
    event_hooks = dict(kwargs.pop("event_hooks", None) or {})
    res_hooks = list(event_hooks.get("response", []))
    if validate_redirect_response not in res_hooks:
        res_hooks.append(validate_redirect_response)
    event_hooks["response"] = res_hooks
    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)

