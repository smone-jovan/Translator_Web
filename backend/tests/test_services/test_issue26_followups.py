"""Issue 26 follow-ups found by re-running the issue's scenarios against main.

A-12: switching workspace is per client; it must not move the process-wide ACTIVE_WORKSPACE that
      unscoped fallbacks of every other device use.
A-16: Gemini rotation spreads requests evenly over the keys still usable today.
A-23: deleting a main book keeps its legacy image folder while a ghost book with the same id
      exists: before per-workspace folders, ghost thread N wrote its images there too."""
import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base, GlobalSetting, Thread
from main import app
from services.ai import secrets


def _memory_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_switching_to_ghost_changes_only_the_requesting_clients_workspace(monkeypatch):
    monkeypatch.setattr(database, "ACTIVE_WORKSPACE", "main")
    with database.SessionLocalMain() as db:
        gs = db.execute(select(GlobalSetting)).scalars().first()
        pin = gs.ghost_pin if (gs and gs.ghost_pin) else "03697"

    res = TestClient(app).post("/api/system/workspace", json={"workspace": "ghost", "pin": pin})

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
    for factory in factories.values():
        with factory() as db:
            db.add(Thread(id=1, title="Buku"))
            db.commit()
    return factories


def test_main_image_folder_is_kept_while_a_ghost_book_may_still_use_it(workspaces, tmp_path):
    main_dir = tmp_path / "uploads" / "images" / "thread_1"
    main_dir.mkdir(parents=True)
    (main_dir / "images_cover.jpg").write_bytes(b"\xff\xd8GHOST-LEGACY")

    res = TestClient(app).delete("/api/threads/1", headers={"X-Workspace": "main"})

    assert res.status_code == 200
    assert (main_dir / "images_cover.jpg").exists()
