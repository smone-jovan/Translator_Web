import socket
import pytest
from fastapi import HTTPException

from services.security import validate_external_url


def test_validate_external_url_valid_public(monkeypatch):
    """Public IPs (e.g. 93.184.216.34) must pass validation."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))
        ],
    )
    # Should not raise
    validate_external_url("https://example.com/chapter-1")


def test_validate_external_url_loopback(monkeypatch):
    """Loopback addresses must be rejected."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        validate_external_url("http://127.0.0.1:8000/api")
    assert exc_info.value.status_code == 400
    assert "private or local network resources is forbidden" in exc_info.value.detail


def test_validate_external_url_private_network(monkeypatch):
    """RFC 1918 private IPs must be rejected."""
    for ip in ["10.0.0.1", "192.168.1.100", "172.16.0.5"]:
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *args, ip_val=ip, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip_val, 80))
            ],
        )
        with pytest.raises(HTTPException) as exc_info:
            validate_external_url(f"http://{ip}/scrape")
        assert exc_info.value.status_code == 400


def test_validate_external_url_link_local_metadata(monkeypatch):
    """Cloud metadata IP (169.254.169.254) must be rejected."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        validate_external_url("http://169.254.169.254/latest/meta-data/")
    assert exc_info.value.status_code == 400


def test_validate_external_url_non_http_scheme():
    """Non-HTTP(S) schemes such as file://, ftp://, gopher:// must be rejected."""
    for url in ["file:///etc/passwd", "ftp://evil.com/file", "gopher://evil.com"]:
        with pytest.raises(HTTPException) as exc_info:
            validate_external_url(url)
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail


def test_validate_external_url_embedded_credentials():
    """URLs with user:password@host must be rejected."""
    with pytest.raises(HTTPException) as exc_info:
        validate_external_url("http://admin:secret@example.com/data")
    assert exc_info.value.status_code == 400
    assert "embedded credentials" in exc_info.value.detail


def test_validate_external_url_unresolvable_hostname(monkeypatch):
    """Unresolvable hostnames should raise HTTPException 400."""
    def mock_getaddrinfo(*args, **kwargs):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    with pytest.raises(HTTPException) as exc_info:
        validate_external_url("https://nonexistent-domain-404-xyz.com")
    assert exc_info.value.status_code == 400
    assert "Cannot resolve hostname" in exc_info.value.detail


def test_validate_external_url_non_global_ips(monkeypatch):
    """Carrier-grade NAT (100.64.0.0/10) and documentation/reserved IPs must be rejected."""
    for non_global_ip in ["100.64.0.1", "100.127.255.254", "198.18.0.1", "192.0.2.1"]:
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *args, ip_val=non_global_ip, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip_val, 80))
            ],
        )
        with pytest.raises(HTTPException) as exc_info:
            validate_external_url(f"http://{non_global_ip}/api")
        assert exc_info.value.status_code == 400
        assert "private or local network resources is forbidden" in exc_info.value.detail


@pytest.mark.asyncio
async def test_safe_redirect_event_hook_catches_internal_redirect(monkeypatch):
    """httpx redirect event hook must intercept redirects to internal resources."""
    from services.security import validate_redirect_response
    import httpx

    # Simulate a 302 response with Location pointing to loopback
    req = httpx.Request("GET", "https://example.com/external")
    resp = httpx.Response(302, request=req, headers={"Location": "http://127.0.0.1:8000/admin"})

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        await validate_redirect_response(resp)
    assert exc_info.value.status_code == 400
    assert "forbidden" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_safe_async_client_normal_response():
    """create_safe_async_client must successfully handle non-redirect responses without awaiting None."""
    from unittest.mock import AsyncMock, patch
    from services.security import create_safe_async_client
    import httpx

    async with create_safe_async_client() as client:
        mock_resp = httpx.Response(200, request=httpx.Request("GET", "https://example.com/valid"))
        with patch.object(client, "_send_single_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_resp
            resp = await client.get("https://example.com/valid")
            assert resp.status_code == 200


