"""A-02: Host header asing ditolak (DNS rebinding); backend hanya bind loopback."""
import pytest
from fastapi.testclient import TestClient

import launcher
from main import app, is_allowed_host


@pytest.mark.parametrize(
    "host",
    ["localhost:8000", "127.0.0.1:8000", "[::1]:8000", "192.168.1.20:5173", "10.0.0.5", "pc-saya.local:5173"],
)
def test_allowed_hosts(host):
    assert is_allowed_host(host)


@pytest.mark.parametrize("host", ["evil.example.com", "rebind.attacker.net:8000", "", "localhost.evil.com"])
def test_foreign_hosts_rejected(host):
    assert not is_allowed_host(host)


def test_request_with_foreign_host_gets_400():
    client = TestClient(app)
    assert client.get("/", headers={"Host": "evil.example.com"}).status_code == 400
    assert client.get("/", headers={"Host": "localhost:8000"}).status_code == 200


def test_launcher_binds_loopback_by_default():
    assert launcher.BACKEND_HOST == "127.0.0.1"
