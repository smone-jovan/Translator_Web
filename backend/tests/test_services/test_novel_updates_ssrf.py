"""
SSRF di adapter Novel Updates (ditemukan reviewer council, ADR-126).

URL detail dari input pengguna (judul berisi "novelupdates.com/series/") dulu diambil apa
adanya dengan curl_cffi tanpa validasi dan redirect diikuti; isinya dikembalikan ke API.
Kini hanya URL https/http ke host novelupdates.com yang diambil, dan setiap hop redirect
divalidasi sebelum diminta.
"""

import socket

import pytest

import services.scrapers.novel_updates as nu_mod
from services.scrapers.novel_updates import NovelUpdatesAdapter

DETAIL_HTML = (
    "<html><head><title>Solo Leveling - Novel Updates</title></head><body>"
    "<div class='seriestitlenu'>Solo Leveling</div>"
    "<div id='editdescription'><p>Sinopsis resmi dari Novel Updates.</p></div>"
    "</body></html>"
)


class _Resp:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


def _fake_session(monkeypatch, responder):
    calls = []

    class FakeSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return responder(url)

    monkeypatch.setattr(nu_mod, "AsyncSession", FakeSession)
    return calls


def _no_search(adapter, monkeypatch):
    async def none(*a, **k):
        return []

    monkeypatch.setattr(adapter, "_search_google", none)
    monkeypatch.setattr(adapter, "_search_yahoo", none)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "http://169.254.169.254/latest/meta-data?novelupdates.com/series/x",
        "http://127.0.0.1:8000/novelupdates.com/series/x",
        "https://evil.example/novelupdates.com/series/x",
        "https://novelupdates.com.evil.example/series/x",
        "file:///etc/passwd#novelupdates.com/series/x",
    ],
)
async def test_non_novelupdates_host_is_never_fetched(monkeypatch, query):
    calls = _fake_session(monkeypatch, lambda url: _Resp(200, "<div id='editdescription'>INTERNAL SECRET</div>"))
    adapter = NovelUpdatesAdapter()
    _no_search(adapter, monkeypatch)

    meta = await adapter.scrape_metadata(query)

    assert calls == []
    assert "INTERNAL SECRET" not in (meta.synopsis or "")


@pytest.mark.asyncio
async def test_redirect_from_novelupdates_to_private_host_is_not_followed(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5" if host == "internal.example" else "104.21.5.10", 0))],
    )

    def responder(url):
        if "novelupdates.com" in url:
            return _Resp(302, headers={"location": "http://internal.example/admin"})
        return _Resp(200, "<div id='editdescription'>INTERNAL SECRET</div>")

    calls = _fake_session(monkeypatch, responder)
    adapter = NovelUpdatesAdapter()
    _no_search(adapter, monkeypatch)

    meta = await adapter.scrape_metadata("https://www.novelupdates.com/series/solo-leveling/")

    assert [c[0] for c in calls] == ["https://www.novelupdates.com/series/solo-leveling/"]
    assert all(c[1].get("allow_redirects") is False for c in calls)
    assert "INTERNAL SECRET" not in (meta.synopsis or "")


@pytest.mark.asyncio
async def test_genuine_novelupdates_url_still_fetched(monkeypatch):
    calls = _fake_session(monkeypatch, lambda url: _Resp(200, DETAIL_HTML))
    adapter = NovelUpdatesAdapter()
    _no_search(adapter, monkeypatch)

    # Tanpa skema, seperti yang biasa ditempel pengguna.
    meta = await adapter.scrape_metadata("www.novelupdates.com/series/solo-leveling/")

    assert [c[0] for c in calls] == ["https://www.novelupdates.com/series/solo-leveling/"]
    assert meta.success
    assert "Sinopsis resmi" in (meta.synopsis or "")
