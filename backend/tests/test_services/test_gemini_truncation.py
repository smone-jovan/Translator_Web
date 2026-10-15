from unittest.mock import AsyncMock, patch

import pytest

from services.ai.base import TRUNCATED_MARKER
from services.ai.gemini import GeminiAdapter


@pytest.mark.asyncio
async def test_chat_completion_preserves_partial_text_when_truncated():
    adapter = GeminiAdapter(api_key="test-key")
    partial_text = "Terjemahan parsial yang berhenti di tengah kalimat"

    with patch.object(adapter, "_try_chat_completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = (partial_text, "length", {})

        result = await adapter.chat_completion([{"role": "user", "content": "Translate"}])

    assert result == partial_text


@pytest.mark.asyncio
async def test_stream_chat_yields_partial_text_before_truncation_marker():
    adapter = GeminiAdapter(api_key="test-key")
    partial_text = "Terjemahan parsial yang berhenti di tengah kalimat"

    with patch.object(adapter, "_try_chat_completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = (partial_text, "length", {})

        chunks = [
            chunk
            async for chunk in adapter.stream_chat(
                [{"role": "user", "content": "Translate"}]
            )
        ]

    assert chunks == [partial_text, TRUNCATED_MARKER]
