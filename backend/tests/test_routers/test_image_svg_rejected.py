"""A-04: SVG/HTML tidak boleh tersimpan atau tersaji sebagai gambar same-origin."""
import io
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from services.image_cacher import guess_image_ext_from_bytes
from services.image_fetcher import is_image_bytes, sniff_raster_ext

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sandbox():
    base = Path("uploads/images").resolve() / "_svg_test_sandbox"
    base.mkdir(parents=True, exist_ok=True)
    yield base
    shutil.rmtree(base, ignore_errors=True)


def test_svg_is_not_an_image():
    assert not is_image_bytes(SVG)
    assert not is_image_bytes(b'<?xml version="1.0"?><svg></svg>')
    assert sniff_raster_ext(SVG) is None


def test_raster_formats_are_sniffed():
    assert sniff_raster_ext(PNG) == "png"
    assert sniff_raster_ext(b"\xff\xd8\xff" + b"\x00" * 16) == "jpeg"
    assert sniff_raster_ext(b"GIF89a" + b"\x00" * 16) == "gif"


def test_cacher_never_labels_svg(  ):
    assert guess_image_ext_from_bytes(SVG) != "svg+xml"


def test_images_route_rejects_svg_extension(client, sandbox):
    (sandbox / "x.svg").write_bytes(SVG)
    resp = client.get("/images/_svg_test_sandbox/x.svg")
    assert resp.status_code == 404


def test_images_route_rejects_html_extension(client, sandbox):
    (sandbox / "x.html").write_bytes(b"<script>alert(1)</script>")
    resp = client.get("/images/_svg_test_sandbox/x.html")
    assert resp.status_code == 404


def test_images_route_serves_png_with_hardening_headers(client, sandbox):
    (sandbox / "ok.png").write_bytes(PNG)
    resp = client.get("/images/_svg_test_sandbox/ok.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in resp.headers["content-security-policy"]


def test_images_route_uses_sniffed_type_not_extension(client, sandbox):
    # SVG berekstensi .png tetap bukan gambar raster -> ditolak
    (sandbox / "fake.png").write_bytes(SVG)
    resp = client.get("/images/_svg_test_sandbox/fake.png")
    assert resp.status_code == 404
