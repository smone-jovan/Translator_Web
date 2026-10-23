"""Issue 26 follow-ups found by re-running the issue's scenarios against main.

A-12: switching workspace is per client; it must not move the process-wide ACTIVE_WORKSPACE that
      unscoped fallbacks of every other device use.
A-16: Gemini rotation spreads requests evenly over the keys still usable today.
A-23: deleting a main book keeps its legacy image folder while a ghost book with the same id
      still links to it: before per-workspace folders, ghost thread N wrote its images there too."""
import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base, Chapter, GlobalSetting, Thread
from main import app
from services.ai import secrets


def _memory_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_switching_to_ghost_changes_only_the_requesting_clients_workspace(monkeypatch):
    # Own databases and session registry: the PIN check, the key sync and the issued ghost
    # session token must not touch state other tests share.
    main_factory, ghost_factory = _memory_factory(), _memory_factory()
    with main_factory() as db:
        db.add(GlobalSetting(ghost_pin="24680"))
        db.commit()
    monkeypatch.setattr(database, "SessionLocalMain", main_factory)
    monkeypatch.setattr(database, "SessionLocalGhost", ghost_factory)
    monkeypatch.setattr(database, "_ghost_sessions", {})
    monkeypatch.setattr(database, "ACTIVE_WORKSPACE", "main")

    res = TestClient(app).post("/api/system/workspace", json={"workspace": "ghost", "pin": "24680"})

    assert res.status_code == 200
    assert database.ACTIVE_WORKSPACE == "main"  # other devices keep their own workspace


def test_gemini_rotation_spreads_requests_evenly_over_healthy_keys(monkeypatch):
    monkeypatch.setattr(secrets, "exhausted_gemini_keys", {})
    monkeypatch.setattr(secrets, "load_secrets", lambda: {"gemini_api_key": ""})
    gs = GlobalSetting(
        llm_provider="gemini", gemini_model="gemini-2.5-flash",
        gemini_api_keys=json.dumps(["A", "B", "C"]), gemini_active_key_index=0,
    )
    secrets.mark_key_exhausted("gemini", "B", "gemini-2.5-flash")

    picks = Counter(secrets.rotate_api_key("gemini", gs) for _ in range(6))

    assert picks == Counter({"A": 3, "C": 3})


@pytest.fixture
def workspaces(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # uploads/ is relative to the working directory
    factories = {"main": _memory_factory(), "ghost": _memory_factory()}
    monkeypatch.setattr(
        database, "get_session_factory",
        lambda ws="main": factories["ghost" if str(ws).lower() == "ghost" else "main"],
    )
    with factories["main"]() as db:
        db.add(Thread(id=1, title="Buku"))
        db.commit()
    return factories


def _main_image_folder(tmp_path):
    main_dir = tmp_path / "uploads" / "images" / "thread_1"
    main_dir.mkdir(parents=True)
    (main_dir / "images_cover.jpg").write_bytes(b"\xff\xd8IMG")
    return main_dir


def test_main_image_folder_is_kept_while_a_ghost_book_still_uses_it(workspaces, tmp_path):
    with workspaces["ghost"]() as db:
        db.add(Thread(id=1, title="Buku Ghost", cover_image="/images/thread_1/images_cover.jpg"))
        db.commit()
    main_dir = _main_image_folder(tmp_path)

    res = TestClient(app).delete("/api/threads/1", headers={"X-Workspace": "main"})

    assert res.status_code == 200
    assert (main_dir / "images_cover.jpg").exists()


def test_main_image_folder_is_kept_while_a_ghost_chapter_still_links_to_it(workspaces, tmp_path):
    with workspaces["ghost"]() as db:
        db.add(Thread(id=1, title="Buku Ghost"))
        db.add(Chapter(thread_id=1, order=1, content_original="![x](/images/thread_1/images_cover.jpg)"))
        db.commit()
    main_dir = _main_image_folder(tmp_path)

    res = TestClient(app).delete("/api/threads/1", headers={"X-Workspace": "main"})

    assert res.status_code == 200
    assert (main_dir / "images_cover.jpg").exists()


def test_main_image_folder_is_removed_when_the_ghost_book_with_that_id_does_not_use_it(workspaces, tmp_path):
    # Ids start at 1 in both databases, so most main books share an id with some ghost book.
    with workspaces["ghost"]() as db:
        db.add(Thread(id=1, title="Buku Ghost", cover_image="/images/ghost/thread_1/images_cover.jpg"))
        db.commit()
    main_dir = _main_image_folder(tmp_path)

    res = TestClient(app).delete("/api/threads/1", headers={"X-Workspace": "main"})

    assert res.status_code == 200
    assert not main_dir.exists()
