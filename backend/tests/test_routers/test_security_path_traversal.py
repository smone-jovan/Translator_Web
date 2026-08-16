import os
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def image_sandbox():
    """Fixture ensuring a clean sandbox directory in uploads/images."""
    base_dir = Path("uploads/images").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    test_sub = base_dir / "test_sandbox"
    test_sub.mkdir(parents=True, exist_ok=True)

    # Create a valid test image
    valid_img = test_sub / "valid_test_img.png"
    valid_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01")

    # Create a sibling directory to test prefix collision
    sibling_dir = base_dir.parent / "images_secret_sandbox"
    sibling_dir.mkdir(parents=True, exist_ok=True)
    sibling_secret = sibling_dir / "secret.txt"
    sibling_secret.write_text("CONFIDENTIAL_DATA", encoding="utf-8")

    yield {
        "base_dir": base_dir,
        "valid_img": valid_img,
        "valid_rel_path": f"test_sandbox/{valid_img.name}",
        "sibling_secret": sibling_secret,
        "sibling_dir": sibling_dir,
    }

    # Cleanup
    if test_sub.exists():
        shutil.rmtree(test_sub, ignore_errors=True)
    if sibling_dir.exists():
        shutil.rmtree(sibling_dir, ignore_errors=True)


def test_serve_image_valid(client, image_sandbox):
    """Valid image inside uploads/images must return 200 and image media type."""
    res = client.get(f"/images/{image_sandbox['valid_rel_path']}")
    assert res.status_code == 200
    assert "image/png" in res.headers.get("content-type", "")
    assert len(res.content) > 0


def test_serve_image_missing(client):
    """Non-existent image must return 404 Not Found."""
    res = client.get("/images/nonexistent_image_xyz_99999.png")
    assert res.status_code == 404
    assert res.json()["detail"] == "Image not found"


def test_serve_image_parent_traversal(client):
    """Relative parent traversal must be blocked with 403 Forbidden or 404 by routing."""
    res = client.get("/images/%2e%2e/%2e%2e/backend/database.py")
    assert res.status_code in [403, 404]
    if res.status_code == 403:
        assert res.json()["detail"] == "Access denied"

    res_subpath = client.get("/images/test_sandbox/%2e%2e/%2e%2e/backend/database.py")
    assert res_subpath.status_code == 403
    assert res_subpath.json()["detail"] == "Access denied"


def test_serve_image_windows_backslash_traversal(client):
    """Windows backslash traversal (..\\ or %5C) must be blocked with 403 Forbidden."""
    res = client.get("/images/..\\..\\backend\\database.py")
    assert res.status_code in [403, 404]
    if res.status_code == 403:
        assert res.json()["detail"] == "Access denied"

    res_encoded = client.get("/images/%2e%2e%5C%2e%2e%5Cbackend%5Cdatabase.py")
    assert res_encoded.status_code in [403, 404]
    if res_encoded.status_code == 403:
        assert res_encoded.json()["detail"] == "Access denied"


def test_serve_image_prefix_collision(client, image_sandbox):
    """Prefix collision against sibling directory must return 403."""
    res = client.get("/images/test_sandbox/%2e%2e/%2e%2e/images_secret_sandbox/secret.txt")
    assert res.status_code == 403
    assert res.json()["detail"] == "Access denied"


def test_serve_image_absolute_drive_path(client):
    """Absolute drive paths (C:/... or D:/...) must be rejected with 403 Forbidden."""
    res = client.get("/images/C:/Windows/win.ini")
    assert res.status_code == 403
    assert res.json()["detail"] == "Access denied"


def test_serve_image_null_byte_and_empty(client):
    """Paths containing null bytes or spaces must be rejected with 403 Forbidden."""
    res = client.get("/images/%00invalid.png")
    assert res.status_code in [400, 403, 404]


def test_serve_image_symlink_escape(client, image_sandbox):
    """Symlinks pointing outside uploads/images must be blocked by canonical containment."""
    base_dir = image_sandbox["base_dir"]
    symlink_path = base_dir / "test_sandbox" / "escape_link.png"
    target_outside = Path("backend/database.py").resolve()

    try:
        if hasattr(os, "symlink"):
            symlink_path.symlink_to(target_outside)
        else:
            pytest.skip("Symlinks not supported on this platform without privileges")
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation requires elevated privileges on Windows; skipping.")

    if symlink_path.exists():
        res = client.get("/images/test_sandbox/escape_link.png")
        assert res.status_code == 403
        assert res.json()["detail"] == "Access denied"
