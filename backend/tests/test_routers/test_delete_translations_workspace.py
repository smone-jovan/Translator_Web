"""Issue 25 (A-10): clearing a book's translations stops that workspace's batch only.

Thread ids are allocated per database, so main and ghost routinely both have a thread 1."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Thread, make_workspace_key
from main import app
from services.background_translator import ActiveBatch, active_batches, recent_finished_batches


def _memory_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with factory() as db:
        db.add(Thread(id=1, title="Same id in both workspaces"))
        db.commit()
    return factory


@pytest.fixture
def dual_workspaces(monkeypatch):
    factories = {"main": _memory_factory(), "ghost": _memory_factory()}
    monkeypatch.setattr(
        "database.get_session_factory",
        lambda ws="main": factories["ghost" if str(ws).lower() == "ghost" else "main"],
    )
    active_batches.clear()
    recent_finished_batches.clear()
    yield factories
    active_batches.clear()
    recent_finished_batches.clear()


def _register_batch(workspace: str) -> ActiveBatch:
    batch = ActiveBatch(
        thread_id=1, chapter_ids=[10, 11], target_lang="Indonesian", model=None, lm_url=None,
        force_extract=False, force_overwrite=False, workspace=workspace,
    )
    active_batches[make_workspace_key(workspace, 1)] = batch
    return batch


def test_clearing_ghost_translations_stops_only_the_ghost_batch(dual_workspaces):
    main_batch = _register_batch("main")
    ghost_batch = _register_batch("ghost")

    res = TestClient(app).delete("/api/threads/1/translations", headers={"X-Workspace": "ghost"})

    assert res.status_code == 200
    assert ghost_batch.is_stopped is True
    assert make_workspace_key("ghost", 1) not in active_batches
    assert main_batch.is_stopped is False
    assert active_batches.get(make_workspace_key("main", 1)) is main_batch
