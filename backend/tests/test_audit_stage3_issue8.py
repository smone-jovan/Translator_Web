import inspect
import pytest
from services.background_translator import BackgroundTranslator, active_batches, ActiveBatch
from services.scrapers.novalpie import NovalpieAdapter


def test_active_batches_no_integer_key_in_background_translator():
    """BackgroundTranslator must not register, query, or pop raw integer thread_id in active_batches."""
    source_start = inspect.getsource(BackgroundTranslator.start_batch)
    source_cleanup = inspect.getsource(BackgroundTranslator._cleanup_batch)
    source_stop = inspect.getsource(BackgroundTranslator.stop_batch)

    # 1. start_batch
    assert "active_batches[thread_id] = batch" not in source_start, (
        "start_batch must not assign integer thread_id to active_batches"
    )
    assert "thread_id in active_batches" not in source_start, (
        "start_batch must not check 'thread_id in active_batches'"
    )

    # 2. _cleanup_batch
    assert "active_batches.pop(batch.thread_id, None)" not in source_cleanup, (
        "_cleanup_batch must not pop integer thread_id"
    )

    # 3. stop_batch
    assert "active_batches.get(thread_id)" not in source_stop, (
        "stop_batch must not fallback to integer thread_id"
    )


def test_batch_router_no_integer_lookup():
    """routers/batch.py must not fallback to active_batches.get(thread_id)."""
    import routers.batch as batch_router
    source_status = inspect.getsource(batch_router.get_batch_status)
    assert "active_batches.get(thread_id)" not in source_status, (
        "get_batch_status must not fallback to active_batches.get(thread_id)"
    )


def test_novalpie_adapter_workspace_propagation():
    """NovalpieAdapter must accept workspace parameter and propagate it to auth & concurrency helpers."""
    sig_init = inspect.signature(NovalpieAdapter.__init__)
    assert "workspace" in sig_init.parameters, "NovalpieAdapter.__init__ must accept 'workspace'"

    adapter = NovalpieAdapter(workspace="ghost")
    assert getattr(adapter, "workspace", None) == "ghost"

    source_headers = inspect.getsource(adapter.get_request_headers)
    assert "self.workspace" in source_headers, "get_request_headers must pass self.workspace"


def test_requirements_txt_synchronization():
    """backend/requirements.txt must not contain crawl4ai and must contain playwright & playwright-stealth."""
    with open("backend/requirements.txt", "r", encoding="utf-8") as f:
        content = f.read()

    assert "crawl4ai" not in content, "crawl4ai is unused and should be removed from requirements.txt"
    assert "playwright" in content, "playwright should be listed in requirements.txt"
    assert "playwright-stealth" in content, "playwright-stealth should be listed in requirements.txt"
