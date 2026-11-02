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


@pytest.mark.asyncio
async def test_batch_worker_extracts_wait_hint_and_sets_cooldown(batch_db, monkeypatch):
    calls = []

    async def rate_limited_then_ok(**kwargs):
        calls.append(kwargs["chapter_id"])
        if len(calls) == 1:
            raise RuntimeError("Upstream service error: HTTP 429: Please try again in 0.05s. (retry in 0.05s)")
        return True

    monkeypatch.setattr(bt.BackgroundTranslator, "_do_translate", staticmethod(rate_limited_then_ok))
    batch = bt.ActiveBatch(
        thread_id=batch_db,
        chapter_ids=[501],
        target_lang="Indonesian",
        model="openai/gpt-oss-120b",
        lm_url=None,
        force_extract=False,
        force_overwrite=False,
    )

    await bt.BackgroundTranslator._run_batch_worker(batch)
    assert calls == [501, 501]
    assert batch.completed == 1
    assert getattr(batch, "rate_limit_cooldown_until", 0) > 0


def test_groq_concurrency_and_pacing():
    # Concurrency for groq is conservative: 1 key -> 1 worker, 2 keys -> 2 workers
    assert bt.BackgroundTranslator._calculate_concurrency_limit("groq", None) == 1
    assert bt.BackgroundTranslator._calculate_concurrency_limit("groq", '["k1", "k2"]') == 2
    assert bt.BackgroundTranslator._calculate_concurrency_limit("groq", '["k1", "k2", "k3", "k4"]') == 3
