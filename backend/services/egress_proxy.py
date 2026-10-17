"""
Forward proxy lokal yang memvalidasi SSRF untuk browser scraper (ADR-126).

Browser Playwright jalur Tier 3 diarahkan ke proxy ini. Untuk setiap koneksi (CONNECT
https/wss, atau request http/ws biasa) proxy me-resolve nama host SENDIRI, menolak bila ada
alamat non-publik, lalu menyambung ke IP yang sudah divalidasi. Dengan begitu semua jalur
jaringan browser (redirect, subresource, popup, form, worker, WebSocket, prefetch) tercakup,
dan tidak ada celah validasi-lalu-resolve-ulang (DNS rebinding).

Hanya mendengarkan di 127.0.0.1 dengan port acak; berjalan di thread daemon tersendiri.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional
from urllib.parse import urlsplit

from services.security import resolve_public_ip as _security_resolve_public_ip

_HEAD_LIMIT = 64 * 1024
_HEAD_TIMEOUT_S = 30.0
_CONNECT_TIMEOUT_S = 20.0
_HOP_BY_HOP = ("proxy-connection:", "proxy-authorization:", "connection:", "keep-alive:")

_FORBIDDEN_RESPONSE = (
    b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: 57\r\n"
    b"X-SSRF-Blocked: 1\r\nConnection: close\r\n\r\n"
    b"Access to private or local network resources is forbidden"
)
_BAD_REQUEST_RESPONSE = b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
_BAD_GATEWAY_RESPONSE = b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


class EgressBlocked(Exception):
    """Tujuan koneksi bukan alamat publik."""


def resolve_public_ip(host: str, port: int) -> str:
    """Titik yang bisa di-monkeypatch tes; default memakai validator SSRF aplikasi."""
    return _security_resolve_public_ip(host, port)


def _split_host_port(authority: str, default_port: int) -> tuple[str, int]:
    authority = authority.strip()
    if authority.startswith("["):
        end = authority.index("]")
        host = authority[1:end]
        rest = authority[end + 1:]
        port = int(rest[1:]) if rest.startswith(":") else default_port
        return host, port
    if authority.count(":") == 1:
        host, port_s = authority.split(":", 1)
        return host, int(port_s)
    return authority, default_port


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass


def _close(writer: Optional[asyncio.StreamWriter]) -> None:
    if writer is None:
        return
    try:
        writer.close()
    except Exception:
        pass


class ValidatingEgressProxy:
    def __init__(self) -> None:
        self.port: Optional[int] = None
        self.handled = 0
        self.blocked = 0
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._error: Optional[BaseException] = None

    @property
    def server_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "ValidatingEgressProxy":
        thread = threading.Thread(target=self._run, name="ssrf-egress-proxy", daemon=True)
        thread.start()
        if not self._ready.wait(10):
            raise RuntimeError("SSRF egress proxy did not start")
        if self._error is not None:
            raise RuntimeError(f"SSRF egress proxy failed to start: {self._error}")
        return self

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            server = loop.run_until_complete(
                asyncio.start_server(self._handle, "127.0.0.1", 0, limit=_HEAD_LIMIT)
            )
            self.port = server.sockets[0].getsockname()[1]
        except BaseException as exc:  # pragma: no cover - port/OS error
            self._error = exc
            self._ready.set()
            return
        self._ready.set()
        loop.run_forever()

    def _count(self, attr: str) -> None:
        with self._lock:
            setattr(self, attr, getattr(self, attr) + 1)

    async def _resolve(self, host: str, port: int) -> str:
        loop = asyncio.get_running_loop()
        try:
            # Dicari saat dipanggil (bukan diikat saat impor) agar bisa di-monkeypatch.
            return await loop.run_in_executor(None, globals()["resolve_public_ip"], host, port)
        except Exception as exc:
            raise EgressBlocked(str(exc)) from exc

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream_writer: Optional[asyncio.StreamWriter] = None
        try:
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), _HEAD_TIMEOUT_S)
            except Exception:
                return
            self._count("handled")
            lines = head.decode("latin-1").split("\r\n")
            try:
                method, target, version = lines[0].split(" ", 2)
            except ValueError:
                writer.write(_BAD_REQUEST_RESPONSE)
                return

            if method.upper() == "CONNECT":
                try:
                    host, port = _split_host_port(target, 443)
                except (ValueError, IndexError):
                    writer.write(_BAD_REQUEST_RESPONSE)
                    return
                ip = await self._resolve(host, port)
                try:
                    up_reader, upstream_writer = await asyncio.wait_for(
                        asyncio.open_connection(ip, port), _CONNECT_TIMEOUT_S
                    )
                except Exception:
                    writer.write(_BAD_GATEWAY_RESPONSE)
                    return
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
            else:
                parts = urlsplit(target)
                if parts.scheme.lower() != "http" or not parts.hostname:
                    writer.write(_BAD_REQUEST_RESPONSE)
                    return
                try:
                    port = parts.port or 80
                except ValueError:
                    writer.write(_BAD_REQUEST_RESPONSE)
                    return
                ip = await self._resolve(parts.hostname, port)
                path = parts.path or "/"
                if parts.query:
                    path += "?" + parts.query
                headers = [h for h in lines[1:] if h and not h.lower().startswith(_HOP_BY_HOP)]
                new_head = (
                    f"{method} {path} {version}\r\n"
                    + "".join(h + "\r\n" for h in headers)
                    + "Connection: close\r\n\r\n"
                )
                try:
                    up_reader, upstream_writer = await asyncio.wait_for(
                        asyncio.open_connection(ip, port), _CONNECT_TIMEOUT_S
                    )
                except Exception:
                    writer.write(_BAD_GATEWAY_RESPONSE)
                    return
                upstream_writer.write(new_head.encode("latin-1"))
                await upstream_writer.drain()

            to_up = asyncio.ensure_future(_pipe(reader, upstream_writer))
            to_client = asyncio.ensure_future(_pipe(up_reader, writer))
            await asyncio.wait({to_up, to_client}, return_when=asyncio.FIRST_COMPLETED)
            # Untuk http biasa, sisi klien boleh selesai mengirim lebih dulu; tunggu respons.
            if not to_client.done() and to_up.done() and method.upper() != "CONNECT":
                await asyncio.wait({to_client}, timeout=_HEAD_TIMEOUT_S)
            for task in (to_up, to_client):
                if not task.done():
                    task.cancel()
        except EgressBlocked:
            self._count("blocked")
            try:
                writer.write(_FORBIDDEN_RESPONSE)
                await writer.drain()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            _close(upstream_writer)
            _close(writer)


_PROXY: Optional[ValidatingEgressProxy] = None
_PROXY_LOCK = threading.Lock()


def get_egress_proxy() -> ValidatingEgressProxy:
    """Proxy tunggal per proses, dinyalakan saat pertama dibutuhkan."""
    global _PROXY
    with _PROXY_LOCK:
        if _PROXY is None:
            _PROXY = ValidatingEgressProxy().start()
        return _PROXY
