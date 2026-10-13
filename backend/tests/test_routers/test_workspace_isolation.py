import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base, Thread, resolve_workspace
from main import app


@pytest.fixture
def mock_dual_workspaces(monkeypatch):
    """Set up two isolated in-memory databases for main and ghost workspaces."""
    engine_test_main = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    engine_test_ghost = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine_test_main)
    Base.metadata.create_all(bind=engine_test_ghost)

    SessionTestMain = sessionmaker(autocommit=False, autoflush=False, bind=engine_test_main)
    SessionTestGhost = sessionmaker(autocommit=False, autoflush=False, bind=engine_test_ghost)

    # Populate unique data in main vs ghost
    with SessionTestMain() as db_main:
        t_main = Thread(title="Main Workspace Book", source_type="manual")
        db_main.add(t_main)
        db_main.commit()

    with SessionTestGhost() as db_ghost:
        t_ghost = Thread(title="Ghost Workspace Secret Book", source_type="manual")
        db_ghost.add(t_ghost)
        db_ghost.commit()

    monkeypatch.setattr("database.SessionLocalMain", SessionTestMain)
    monkeypatch.setattr("database.SessionLocalGhost", SessionTestGhost)

    def mock_get_session_factory(ws: str = "main"):
        if str(ws).lower() == "ghost":
            return SessionTestGhost
        return SessionTestMain

    monkeypatch.setattr("database.get_session_factory", mock_get_session_factory)

    yield {
        "SessionMain": SessionTestMain,
        "SessionGhost": SessionTestGhost,
    }


def test_resolve_workspace_from_headers_and_cookies():
    """Test resolution of workspace from request headers and cookies."""
    class DummyRequest:
        def __init__(self, headers=None, cookies=None):
            self.headers = headers or {}
            self.cookies = cookies or {}

    # Header takes precedence
    req1 = DummyRequest(headers={"X-Workspace": "ghost"})
    assert resolve_workspace(req1) == "ghost"

    req2 = DummyRequest(headers={"x-workspace": "MAIN"})
    assert resolve_workspace(req2) == "main"

    # Cookie fallback
    req3 = DummyRequest(cookies={"readomni_workspace": "ghost"})
    assert resolve_workspace(req3) == "ghost"

    # Default fallback to main on invalid or empty
    req4 = DummyRequest(headers={"X-Workspace": "invalid_subspace"})
    assert resolve_workspace(req4) == "main"

    req5 = DummyRequest()
    assert resolve_workspace(req5) == "main"

    assert resolve_workspace(None) == "main"


def test_system_current_workspace_endpoint():
    """GET /api/system/workspace/current respects request headers."""
    client = TestClient(app)

    res_main = client.get("/api/system/workspace/current", headers={"X-Workspace": "main"})
    assert res_main.status_code == 200
    assert res_main.json() == {"workspace": "main"}

    res_ghost = client.get("/api/system/workspace/current", headers={"X-Workspace": "ghost"})
    assert res_ghost.status_code == 200
    assert res_ghost.json() == {"workspace": "ghost"}


def test_threads_workspace_data_isolation(mock_dual_workspaces):
    """GET /api/threads should return threads strictly isolated to the specified workspace."""
    client = TestClient(app)

    # 1. Fetch threads with X-Workspace: main
    resp_main = client.get("/api/threads", headers={"X-Workspace": "main"})
    assert resp_main.status_code == 200
    main_threads = resp_main.json()
    main_titles = [t["title"] for t in main_threads]
    assert "Main Workspace Book" in main_titles
    assert "Ghost Workspace Secret Book" not in main_titles

    # 2. Fetch threads with X-Workspace: ghost
    resp_ghost = client.get("/api/threads", headers={"X-Workspace": "ghost"})
    assert resp_ghost.status_code == 200
    ghost_threads = resp_ghost.json()
    ghost_titles = [t["title"] for t in ghost_threads]
    assert "Ghost Workspace Secret Book" in ghost_titles
    assert "Main Workspace Book" not in ghost_titles


def test_batch_status_workspace_isolation(mock_dual_workspaces):
    """Batch progress in active_batches must not leak or collide across workspaces."""
    from services.background_translator import active_batches, ActiveBatch
    client = TestClient(app)

    # Simulate thread_id=1 active in ghost, but thread_id=1 NOT active in main
    ghost_batch = ActiveBatch(
        thread_id=1,
        chapter_ids=[10, 11, 12],
        target_lang="Indonesian",
        model="test-model",
        lm_url="http://test.local",
        force_extract=False,
        force_overwrite=True,
        workspace="ghost",
    )
    ghost_batch.completed = 2
    ghost_batch.current_chapter_id = 10
    ghost_batch.current_chapter_title = "Ghost Chapter 1"
    ghost_batch.is_waiting = False
    active_batches[("ghost", 1)] = ghost_batch

    try:
        # Requesting batch status from main workspace should return inactive
        resp_main = client.get("/api/threads/1/batch-status", headers={"X-Workspace": "main"})
        assert resp_main.status_code == 200
        assert resp_main.json()["active"] is False

        # Requesting batch status from ghost workspace should return active
        resp_ghost = client.get("/api/threads/1/batch-status", headers={"X-Workspace": "ghost"})
        assert resp_ghost.status_code == 200
        data = resp_ghost.json()
        assert data["active"] is True
        assert data["current_chapter_title"] == "Ghost Chapter 1"

        # Active batches endpoint isolation
        resp_active_main = client.get("/api/threads/active-batch", headers={"X-Workspace": "main"})
        assert resp_active_main.status_code == 200
        assert resp_active_main.json()["active"] is False

        resp_active_ghost = client.get("/api/threads/active-batch", headers={"X-Workspace": "ghost"})
        assert resp_active_ghost.status_code == 200
        assert resp_active_ghost.json()["active"] is True
    finally:
        active_batches.pop(("ghost", 1), None)

