import inspect

import pytest

from routers import images, scrape

# Handler yang hanya memakai DB sinkron (dan I/O file lokal) harus berupa `def`.
# FastAPI menjalankan `def` di threadpool, sehingga tidak memblokir event loop.
SYNC_DB_HANDLERS = [
    (images, "get_thread_image_cache_status"),
    (images, "list_thread_images"),
    (images, "clear_image_cache"),
    (scrape, "save_metadata_route"),
]


@pytest.mark.parametrize("module,name", SYNC_DB_HANDLERS)
def test_db_only_handler_is_sync_def(module, name):
    handler = getattr(module, name)

    assert not inspect.iscoroutinefunction(handler), f"{name} harus `def`, bukan `async def`"


def test_start_image_cache_stays_async_because_it_schedules_a_task():
    # start_thread_image_cache memanggil asyncio.create_task, yang butuh event loop
    # yang sedang berjalan. Jika diubah ke `def`, pemanggilan itu gagal di threadpool.
    assert inspect.iscoroutinefunction(images.start_thread_image_cache)
