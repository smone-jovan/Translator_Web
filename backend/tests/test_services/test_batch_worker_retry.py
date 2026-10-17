from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.background_translator as bt
from database import Base, Chapter, GlobalSetting, Thread


@pytest.fixture
def batch_db(monkeypatch):
    """In-memory DB yang dipakai get_session() milik batch worker."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with Factory() as db:
        db.add(GlobalSetting(llm_provider="lm_studio"))
        thread = Thread(title="T")
        db.add(thread)
        db.flush()
        db.add(Chapter(id=501, thread_id=thread.id, order=1, title_original="Ch 1"))
        db.commit()
        thread_id = thread.id

    @contextmanager
    def fake_get_session(workspace="main"):
        db = Factory()
        db._workspace = workspace
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(bt, "get_session", fake_get_session)
    monkeypatch.setattr(bt, "RETRY_BASE_DELAY", 0.01)
    return thread_id


@pytest.mark.asyncio
async def test_retryable_error_is_requeued_instead_of_killing_worker(batch_db, monkeypatch):
    # Arrange: panggilan pertama kena 429 (retryable, di-raise ulang oleh _do_translate),
    # panggilan kedua sukses.
    calls = []

    async def flaky_translate(**kwargs):
        calls.append(kwargs["chapter_id"])
        if len(calls) == 1:
            raise RuntimeError("429 Too Many Requests: rate limit")
        return True

    monkeypatch.setattr(bt.BackgroundTranslator, "_do_translate", staticmethod(flaky_translate))
    batch = bt.ActiveBatch(
        thread_id=batch_db,
        chapter_ids=[501],
        target_lang="Indonesian",
        model=None,
        lm_url=None,
        force_extract=False,
        force_overwrite=False,
    )

    # Act
    await bt.BackgroundTranslator._run_batch_worker(batch)

    # Assert: bab dicoba ulang lalu selesai, bukan worker mati diam-diam
    assert calls == [501, 501]
    assert batch.completed == 1
    assert batch.failed_ids == []
    assert batch.status == "completed"
