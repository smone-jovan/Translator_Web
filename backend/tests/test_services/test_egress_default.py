"""A-18: koneksi httpx/curl_cffi keluar lewat proxy egress yang memvalidasi IP saat connect."""
import httpx

from services import security
from services.egress_proxy import get_egress_proxy


def test_safe_client_routes_through_egress_proxy():
    client = security.create_safe_async_client()
    mounts = [m for m in client._mounts.values() if m is not None]
    assert mounts, "client harus memakai proxy transport"
    assert get_egress_proxy().server_url.endswith(str(get_egress_proxy().port))


def test_egress_proxies_for_curl_cffi():
    proxies = security.egress_proxies()
    assert proxies["http"] == proxies["https"] == get_egress_proxy().server_url


def test_explicit_transport_is_not_overridden():
    client = security.create_safe_async_client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert not [m for m in client._mounts.values() if m is not None]
