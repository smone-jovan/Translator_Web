import asyncio
from unittest.mock import patch

from services.ai.lm_studio import LMStudioAdapter

MESSAGES = [{"role": "user", "content": "hi"}]


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, content="Halo", finish_reason="stop", reasoning=None):
        message = {"content": content}
        if reasoning:
            message["reasoning_content"] = reasoning
        self._body = {"choices": [{"message": message, "finish_reason": finish_reason}]}

    def json(self):
        return self._body


def run_with(response, call):
    sent = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            sent.append(json)
            return response

    with patch("services.ai.lm_studio.httpx.AsyncClient", FakeClient):
        result = asyncio.run(call())
    return result, sent


def test_detailed_returns_text_and_finish_reason():
    adapter = LMStudioAdapter(model="index-translate-2b")

    result, _ = run_with(FakeResponse("Halo dunia", "length"), lambda: adapter.chat_completion_detailed(MESSAGES))

    assert (result.text, result.finish_reason) == ("Halo dunia", "length")


def test_detailed_keeps_reasoning_wrapped_like_chat_completion():
    adapter = LMStudioAdapter(model="index-translate-2b")

    result, _ = run_with(FakeResponse("Halo", reasoning="mikir"), lambda: adapter.chat_completion_detailed(MESSAGES))

    assert result.text.startswith("<think>\nmikir\n</think>") and result.text.endswith("Halo")


def test_extra_parameters_are_added_to_the_payload():
    adapter = LMStudioAdapter(model="index-translate-2b")

    _, sent = run_with(
        FakeResponse(),
        lambda: adapter.chat_completion_detailed(MESSAGES, temperature=0.0, max_tokens=1024, extra={"repeat_penalty": 1.1}),
    )

    (payload,) = sent
    assert payload["repeat_penalty"] == 1.1
    assert payload["max_tokens"] == 1024 and payload["temperature"] == 0.0
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_plain_chat_completion_is_unchanged_and_sends_no_penalty():
    adapter = LMStudioAdapter(model="index-translate-2b")

    text, sent = run_with(FakeResponse("Halo"), lambda: adapter.chat_completion(MESSAGES, temperature=0.0))

    assert text == "Halo"
    assert "repeat_penalty" not in sent[0] and "frequency_penalty" not in sent[0]


def test_extra_cannot_override_core_fields():
    adapter = LMStudioAdapter(model="index-translate-2b")

    _, sent = run_with(
        FakeResponse(),
        lambda: adapter.chat_completion_detailed(MESSAGES, extra={"messages": [], "stream": True, "model": "x"}),
    )

    assert sent[0]["messages"] == MESSAGES and sent[0]["stream"] is False and sent[0]["model"] == "index-translate-2b"
