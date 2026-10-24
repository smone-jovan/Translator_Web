import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from database import LorebookEntry, Thread, get_db
from main import app
from services.ai.base import BaseAIProviderAdapter


class RecordingProvider(BaseAIProviderAdapter):
    def __init__(self):
        self.calls = []

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        return "Lin Dong tersenyum."

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        yield "Lin Dong tersenyum."


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _post(client, provider, model, thread_id=None):
    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider):
        return client.post(
            "/api/translate",
            json={"text": "林动笑了。", "target_lang": "Indonesian", "model": model, "thread_id": thread_id},
        )


def test_index_translate_model_gets_single_readme_style_user_message(client, db_session):
    provider = RecordingProvider()
    resp = _post(client, provider, "IndexTeam/Index-Translate-2B-GGUF")

    assert resp.status_code == 200
    (messages,) = provider.calls
    assert [m["role"] for m in messages] == ["user"]
    assert messages[0]["content"] == "请将以下文本翻译为印尼语，直接输出翻译结果，不要进行任何解释。\n\n林动笑了。"


def test_index_translate_model_receives_matching_glossary_terms(client, db_session):
    thread = Thread(title="novel")
    db_session.add(thread)
    db_session.commit()
    db_session.add(LorebookEntry(thread_id=thread.id, original_term="林动", translated_term="Lin Dong"))
    db_session.commit()

    provider = RecordingProvider()
    resp = _post(client, provider, "IndexTeam/Index-Translate-2B-GGUF", thread_id=thread.id)

    assert resp.status_code == 200
    (messages,) = provider.calls
    assert "【硬性要求】专名/术语对照: 林动→Lin Dong" in messages[0]["content"]


def test_other_models_keep_system_plus_user_prompt(client, db_session):
    provider = RecordingProvider()
    resp = _post(client, provider, "gemma-3-4b")

    assert resp.status_code == 200
    (messages,) = provider.calls
    assert [m["role"] for m in messages] == ["system", "user"]
