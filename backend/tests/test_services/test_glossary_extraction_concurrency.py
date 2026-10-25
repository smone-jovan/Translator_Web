import asyncio
from unittest.mock import MagicMock, patch

import pytest

from services.context_engine import ContextEngine


class _GatedProvider:
    """chat_completion blocks until `release` is set, so overlapping calls are observable."""

    def __init__(self, release: asyncio.Event):
        self.release = release
        self.started = 0

    async def chat_completion(self, messages, temperature=0.2):
        self.started += 1
        await self.release.wait()
        return "- 宁凡 -> Ning Fan"


@pytest.mark.asyncio
async def test_extractions_overlap_but_saves_are_serialized(db_session):
    # Arrange: two chapters extract at once; saving to the lorebook must still take turns
    release = asyncio.Event()
    provider = _GatedProvider(release)
    save_lock = asyncio.Lock()
    in_save = 0
    max_in_save = 0

    def slow_save(db, thread_id, text):
        nonlocal in_save, max_in_save
        in_save += 1
        max_in_save = max(max_in_save, in_save)
        in_save -= 1

    async def run():
        await ContextEngine.extract_glossary_pass(
            db_session, 1, "原文", "http://localhost:1234", "m", "English", save_lock=save_lock
        )

    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=provider), \
         patch.object(ContextEngine, "auto_save_glossary", side_effect=slow_save):
        # Act
        tasks = [asyncio.create_task(run()) for _ in range(2)]
        for _ in range(50):
            if provider.started == 2:
                break
            await asyncio.sleep(0.01)
        both_in_flight = provider.started == 2
        release.set()
        await asyncio.gather(*tasks)

    # Assert
    assert both_in_flight, "the second extraction waited for the first one's LLM call"
    assert max_in_save == 1


@pytest.mark.asyncio
async def test_save_waits_while_lock_is_held(db_session):
    release = asyncio.Event()
    release.set()
    save_lock = asyncio.Lock()
    saved = MagicMock()

    with patch("services.ai.factory.AIProviderFactory.get_provider", return_value=_GatedProvider(release)), \
         patch.object(ContextEngine, "auto_save_glossary", saved):
        async with save_lock:
            task = asyncio.create_task(
                ContextEngine.extract_glossary_pass(
                    db_session, 1, "原文", "http://localhost:1234", "m", "English", save_lock=save_lock
                )
            )
            await asyncio.sleep(0.05)
            saved.assert_not_called()
        await task

    saved.assert_called_once()
