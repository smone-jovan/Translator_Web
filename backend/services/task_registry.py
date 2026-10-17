"""Strong references for fire-and-forget asyncio tasks.

The event loop keeps only weak references to tasks, so a task whose result nobody holds
can be garbage-collected before it finishes (see the asyncio.create_task docs).
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

_background_tasks: set[asyncio.Task] = set()


def spawn_background_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """Schedule coro and keep the task referenced until it completes."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
