import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from services.background_translator import BackgroundTranslator, active_batches, master_batch_queue
import services.background_translator

# Mock out _run_batch_worker so we don't actually do any DB or AI calls
@pytest.fixture(autouse=True)
def cleanup_master_queue():
    """Ensure state is clean before and after each test."""
    active_batches.clear()
    
    # Clear queue
    while not master_batch_queue.empty():
        try:
            master_batch_queue.get_nowait()
            master_batch_queue.task_done()
        except asyncio.QueueEmpty:
            break
            
    # Reset master task
    if services.background_translator.master_worker_task:
        services.background_translator.master_worker_task.cancel()
        services.background_translator.master_worker_task = None
        
    yield
    
    active_batches.clear()
    if services.background_translator.master_worker_task:
        services.background_translator.master_worker_task.cancel()
        services.background_translator.master_worker_task = None

@pytest.mark.asyncio
async def test_sequential_queueing_behavior():
    """
    Test 1: When Thread 1 is started, it becomes active (is_waiting = False).
    When Thread 2 is started immediately after, it queues up (is_waiting = True).
    """
    # Arrange: Mock the worker so it hangs (simulating a long translation)
    mock_worker = AsyncMock()
    async def fake_worker(batch):
        # Hang forever so it blocks the master loop
        await asyncio.sleep(10.0)
    mock_worker.side_effect = fake_worker
    
    with patch("services.background_translator.BackgroundTranslator._run_batch_worker", new=mock_worker):
        # Act
        await BackgroundTranslator.start_batch(
            thread_id=1,
            chapter_ids=[101, 102],
            target_lang="Indonesian"
        )
        
        # Give asyncio loop a tiny moment to switch context so master_loop can pick up Thread 1
        await asyncio.sleep(0.1)
        
        await BackgroundTranslator.start_batch(
            thread_id=2,
            chapter_ids=[201, 202],
            target_lang="Indonesian"
        )
        
        # Give asyncio loop a tiny moment
        await asyncio.sleep(0.1)
        
        # Assert
        batch_1 = active_batches.get(("main", 1))
        batch_2 = active_batches.get(("main", 2))

        assert batch_1 is not None, "Thread 1 should be in active_batches"
        assert batch_2 is not None, "Thread 2 should be in active_batches"
        
        # Thread 1 should be picked up by master_loop and NOT waiting
        assert batch_1.is_waiting is False, "Thread 1 should be active (is_waiting=False)"
        
        # Thread 2 should still be waiting in the queue
        assert batch_2.is_waiting is True, "Thread 2 should be waiting in queue (is_waiting=True)"


@pytest.mark.asyncio
async def test_sequential_processing_transition():
    """
    Test 2: When Thread 1 finishes, Thread 2 automatically starts.
    """
    mock_worker = AsyncMock()
    # We don't sleep forever here, just a quick sleep to simulate work
    async def fast_worker(batch):
        await asyncio.sleep(0.1)
    mock_worker.side_effect = fast_worker
    
    with patch("services.background_translator.BackgroundTranslator._run_batch_worker", new=mock_worker):
        await BackgroundTranslator.start_batch(thread_id=1, chapter_ids=[101], target_lang="Indonesian")
        await BackgroundTranslator.start_batch(thread_id=2, chapter_ids=[201], target_lang="Indonesian")
        
        # Wait enough time for Thread 1 to finish and Thread 2 to be picked up
        await asyncio.sleep(0.3)

        batch_2 = active_batches.get(("main", 2))
        assert batch_2 is not None
        assert batch_2.is_waiting is False, "Thread 2 should become active after Thread 1 finishes"

@pytest.mark.asyncio
async def test_graceful_cancellation():
    """
    Test 3: Graceful cancellation via stop_batch.
    - Stopping Thread 1 while active should immediately promote Thread 2.
    - Stopping Thread 3 while waiting should remove it completely.
    """
    mock_worker = AsyncMock()
    async def slow_worker(batch):
        # We catch cancellation so we don't spam logs
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            pass
    mock_worker.side_effect = slow_worker

    with patch("services.background_translator.BackgroundTranslator._run_batch_worker", new=mock_worker):
        # Start 3 threads
        await BackgroundTranslator.start_batch(1, [101], "Id")
        await asyncio.sleep(0.05)
        await BackgroundTranslator.start_batch(2, [201], "Id")
        await BackgroundTranslator.start_batch(3, [301], "Id")

        await asyncio.sleep(0.1) # Let Thread 1 be picked up

        assert active_batches[("main", 1)].is_waiting is False
        assert active_batches[("main", 2)].is_waiting is True
        assert active_batches[("main", 3)].is_waiting is True

        # Cancel Thread 3 (waiting)
        await BackgroundTranslator.stop_batch(3)
        assert ("main", 3) not in active_batches, "Thread 3 should be removed entirely"

        # Cancel Thread 1 (active)
        await BackgroundTranslator.stop_batch(1)
        assert ("main", 1) not in active_batches, "Thread 1 should be removed entirely"

        # Give master loop a moment to pick up Thread 2
        await asyncio.sleep(0.2)

        assert ("main", 2) in active_batches
        assert active_batches[("main", 2)].is_waiting is False, "Thread 2 should now be active"

def test_calculate_concurrency_limit_lm_studio():
    # LM Studio should ALWAYS be 1 for local VRAM safety
    limit = BackgroundTranslator._calculate_concurrency_limit("lm_studio", None)
    assert limit == 1

@pytest.mark.asyncio
@pytest.mark.parametrize("detected,expected", [(4, 4), (1, 1), (None, 1), (20, 8)])
async def test_lm_studio_concurrency_follows_loaded_parallel_slots(detected, expected):
    # Parallel load: use every slot LM Studio reports for the model (index-translate loaded with 4 -> 4)
    with patch("services.lm_slots.detect_parallel", AsyncMock(return_value=detected)) as probe:
        limit = await BackgroundTranslator._resolve_lm_studio_concurrency("http://localhost:1234", "index-translate")
    assert limit == expected
    probe.assert_awaited_once_with("http://localhost:1234", "index-translate")

@pytest.mark.asyncio
async def test_lm_studio_concurrency_is_one_without_model():
    with patch("services.lm_slots.detect_parallel", AsyncMock(return_value=4)) as probe:
        assert await BackgroundTranslator._resolve_lm_studio_concurrency("http://localhost:1234", None) == 1
    probe.assert_not_awaited()

def test_calculate_concurrency_limit_cloud_providers():
    # Default for cloud is 2 or 3 per key
    limit = BackgroundTranslator._calculate_concurrency_limit("gemini", None)
    assert limit >= 2
    
    limit = BackgroundTranslator._calculate_concurrency_limit("openai", None)
    assert limit >= 2

def test_calculate_concurrency_limit_with_multiple_keys():
    # If 2 keys are provided for gemini, it should scale (2 * 3 = 6)
    limit = BackgroundTranslator._calculate_concurrency_limit("gemini", '["key1", "key2"]')
    assert limit == 6
    
    # Cap at 20
    many_keys = '["k1"' + ',"k2"' * 10 + ']'
    limit = BackgroundTranslator._calculate_concurrency_limit("gemini", many_keys)
    assert limit <= 20

@pytest.mark.asyncio
async def test_enforce_pacing_rotates_keys_in_db(db_session):
    """Test that _enforce_pacing rotates and persists the active key index in GlobalSetting."""
    import json
    from database import GlobalSetting
    from sqlalchemy import select
    
    gs = GlobalSetting(
        llm_provider="gemini",
        gemini_api_keys=json.dumps(["keyA", "keyB", "keyC"]),
        gemini_active_key_index=0
    )
    db_session.add(gs)
    db_session.commit()
    
    # Call _enforce_pacing first time
    await BackgroundTranslator._enforce_pacing(model="gemini-3.5-flash-lite", gs=gs)
    db_session.refresh(gs)
    assert gs.gemini_active_key_index == 1, "First pacing call should advance active key to 1"
    
    # Call _enforce_pacing second time
    await BackgroundTranslator._enforce_pacing(model="gemini-3.5-flash-lite", gs=gs)
    db_session.refresh(gs)
    assert gs.gemini_active_key_index == 2, "Second pacing call should advance active key to 2"
    
    # Call _enforce_pacing third time (wrap around)
    await BackgroundTranslator._enforce_pacing(model="gemini-3.5-flash-lite", gs=gs)
    db_session.refresh(gs)
    assert gs.gemini_active_key_index == 0, "Third pacing call should wrap around to 0"


@pytest.mark.asyncio
async def test_start_batch_load_mode_storage():
    """Verify that start_batch correctly stores load_mode on the ActiveBatch object."""
    mock_worker = AsyncMock()
    with patch("services.background_translator.BackgroundTranslator._run_batch_worker", new=mock_worker):
        await BackgroundTranslator.start_batch(
            thread_id=99,
            chapter_ids=[1],
            target_lang="Indonesian",
            load_mode="hard"
        )
        batch = active_batches.get(("main", 99))
        assert batch is not None
        assert getattr(batch, "load_mode", None) == "hard"

