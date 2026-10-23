"""A-31: batas byte saat unduh/upload dan pemeriksaan zip bomb."""
import io
import zipfile

import httpx
import pytest
from fastapi import HTTPException

from services.security import (
    ResponseTooLarge,
    check_zip_safe,
    cap_response_size,
    read_upload_limited,
)


class _FakeUpload:
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    async def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)


def _client(handler, max_bytes: int = 100) -> httpx.AsyncClient:
    return cap_response_size(httpx.AsyncClient(transport=httpx.MockTransport(handler)), max_bytes)


@pytest.mark.asyncio
async def test_cap_response_size_returns_full_small_body():
    async with _client(lambda r: httpx.Response(200, content=b"hello")) as c:
        resp = await c.get("http://x.test/")
    assert resp.status_code == 200 and resp.content == b"hello"


@pytest.mark.asyncio
async def test_cap_response_size_rejects_by_content_length():
    async with _client(lambda r: httpx.Response(200, content=b"x" * 50), 10) as c:
        with pytest.raises(ResponseTooLarge):
            await c.get("http://x.test/")


@pytest.mark.asyncio
async def test_cap_response_size_aborts_chunked_body_over_limit():
    def handler(request):
        async def gen():
            for _ in range(10):
                yield b"x" * 10

        return httpx.Response(200, content=gen())  # tanpa Content-Length

    async with _client(handler, 25) as c:
        with pytest.raises(ResponseTooLarge):
            await c.get("http://x.test/")


@pytest.mark.asyncio
async def test_read_upload_limited_ok_and_too_large():
    assert await read_upload_limited(_FakeUpload(b"abc"), max_bytes=10) == b"abc"
    with pytest.raises(HTTPException) as exc:
        await read_upload_limited(_FakeUpload(b"x" * 50), max_bytes=10)
    assert exc.value.status_code == 413


def _zip_bytes(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("a.xhtml", payload)
    return buf.getvalue()


def test_check_zip_safe_accepts_normal_and_rejects_bomb():
    check_zip_safe(_zip_bytes(b"hello world" * 10), max_total=10_000, max_ratio=100)
    bomb = _zip_bytes(b"\x00" * 5_000_000)
    with pytest.raises(HTTPException) as exc:
        check_zip_safe(bomb, max_total=1_000_000, max_ratio=100)
    assert exc.value.status_code == 413
    with pytest.raises(HTTPException):
        check_zip_safe(b"not a zip", max_total=1_000_000, max_ratio=100)
