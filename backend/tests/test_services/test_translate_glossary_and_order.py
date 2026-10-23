"""Bukti: (1) batch memproses bab sesuai urutan chapter_ids, (2) glossary (lorebook) benar-benar
masuk ke messages LLM saat _do_translate, dan edit istilah langsung terbaca translate berikutnya."""
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.background_translator as bt
from database import Base, Chapter, GlobalSetting, LorebookEntry, Thread


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with Factory() as db:
        db.add(GlobalSetting(llm_provider="lm_studio"))
        thread = Thread(title="T")
        db.add(thread)
        db.flush()
        for cid, order in ((3, 3), (1, 1), (2, 2)):
            db.add(
                Chapter(
                    id=cid, thread_id=thread.id, order=order, title_original=f"Ch {order}",
                    content_original="云逸在山门前遇见了林月。" * 5,
                )
            )
        db.add(LorebookEntry(thread_id=thread.id, original_term="云逸", translated_term="Yun Yi", is_locked=True))
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

    async def no_pacing(*args, **kwargs):
        return None

    monkeypatch.setattr(bt, "get_session", fake_get_session)
    monkeypatch.setattr(bt.BackgroundTranslator, "_enforce_pacing", staticmethod(no_pacing))
    return {"thread_id": thread_id, "factory": Factory}


@pytest.mark.asyncio
async def test_batch_processes_chapters_in_requested_order(env, monkeypatch):
    # Arrange: urutan sengaja bukan menaik; harus dihormati apa adanya.
    calls = []

    async def record(**kwargs):
        calls.append(kwargs["chapter_id"])
        return True

    monkeypatch.setattr(bt.BackgroundTranslator, "_do_translate", staticmethod(record))
    batch = bt.ActiveBatch(
        thread_id=env["thread_id"], chapter_ids=[3, 1, 2], target_lang="Indonesian",
        model=None, lm_url=None, force_extract=False, force_overwrite=False,
    )

    # Act
    await bt.BackgroundTranslator._run_batch_worker(batch)

    # Assert
    assert calls == [3, 1, 2]


class _CapturingProvider:
    def __init__(self, sink):
        self.sink = sink

    async def stream_chat(self, messages, **kwargs):
        self.sink.append(messages)
        yield "Yun Yi bertemu Lin Yue di depan gerbang gunung."


@pytest.mark.asyncio
async def test_do_translate_injects_locked_glossary_into_llm_messages(env, monkeypatch):
    sent = []
    monkeypatch.setattr(
        bt.AIProviderFactory, "get_provider", staticmethod(lambda **kw: _CapturingProvider(sent))
    )

    ok = await bt.BackgroundTranslator._do_translate(
        chapter_id=1, thread_id=env["thread_id"], target_lang="Indonesian",
        load_mode="hard", workspace="main",
    )

    assert ok is True
    system_prompt = sent[0][0]["content"]
    assert "云逸" in system_prompt and "Yun Yi" in system_prompt


@pytest.mark.asyncio
async def test_glossary_edit_is_used_by_the_next_translation_without_restart(env, monkeypatch):
    sent = []
    monkeypatch.setattr(
        bt.AIProviderFactory, "get_provider", staticmethod(lambda **kw: _CapturingProvider(sent))
    )
    with env["factory"]() as db:
        entry = db.query(LorebookEntry).filter_by(original_term="云逸").one()
        entry.translated_term = "Yunyi Baru"
        db.commit()

    await bt.BackgroundTranslator._do_translate(
        chapter_id=2, thread_id=env["thread_id"], target_lang="Indonesian",
        load_mode="hard", workspace="main",
    )

    assert "Yunyi Baru" in sent[0][0]["content"]
