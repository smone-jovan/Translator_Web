"""Judul bab/novel dan sinopsis harus memakai glossary thread (konsisten dengan isi bab)."""
import pytest
from fastapi.testclient import TestClient

from database import Chapter, LorebookEntry, Thread, get_db
from main import app
from services.context_engine import ContextEngine


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def thread(db_session):
    t = Thread(title="T", original_title="云逸传", synopsis="")
    db_session.add(t)
    db_session.flush()
    db_session.add(Chapter(thread_id=t.id, order=1, title_original="第1章 云逸出山"))
    db_session.add(LorebookEntry(thread_id=t.id, original_term="云逸", translated_term="Yun Yi", is_locked=True))
    db_session.add(LorebookEntry(thread_id=t.id, original_term="林月", translated_term="Lin Yue", is_locked=True))
    db_session.add(
        LorebookEntry(thread_id=t.id, original_term="云逸传", translated_term="Kisah Yun Yi", is_archived=True)
    )
    db_session.commit()
    return t


def test_glossary_hint_lists_only_active_terms_found_in_text(db_session, thread):
    hint = ContextEngine.build_glossary_hint(db_session, thread.id, "第1章 云逸出山")

    assert "云逸" in hint and "Yun Yi" in hint
    assert "林月" not in hint  # tidak muncul di teks
    assert "Kisah Yun Yi" not in hint  # diarsipkan


def test_glossary_hint_is_empty_when_no_term_matches(db_session, thread):
    assert ContextEngine.build_glossary_hint(db_session, thread.id, "完全无关的标题") == ""


def test_translate_titles_sends_glossary_to_llm(client, db_session, thread, monkeypatch):
    from routers import polish

    captured = []

    class FakeProvider:
        async def chat_completion(self, messages, **kwargs):
            captured.append(messages)
            return "[CHAPTER_0]: Bab 1 Yun Yi Turun Gunung"

    monkeypatch.setattr(polish.AIProviderFactory, "get_provider", lambda **kw: FakeProvider())

    resp = client.post(f"/api/threads/{thread.id}/translate-titles?target_lang=Indonesian&chapter_id=1")

    assert resp.status_code == 200
    assert captured, "LLM tidak dipanggil"
    system_prompt = captured[-1][0]["content"]
    assert "云逸" in system_prompt and "Yun Yi" in system_prompt
