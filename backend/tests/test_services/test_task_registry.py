import ast
import asyncio
import pathlib

import pytest

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_spawned_task_is_referenced_until_it_finishes():
    from services.task_registry import _background_tasks, spawn_background_task

    # Arrange
    release = asyncio.Event()

    async def job():
        await release.wait()
        return "done"

    # Act
    task = spawn_background_task(job())

    # Assert: strongly held while running, released once finished
    assert task in _background_tasks
    release.set()
    assert await task == "done"
    await asyncio.sleep(0)
    assert task not in _background_tasks


def _discarded_task_calls(path: pathlib.Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            continue
        func = node.value.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"create_task", "ensure_future"}
            and isinstance(func.value, ast.Name)
            and func.value.id == "asyncio"
        ):
            lines.append(node.lineno)
    return lines


def test_no_fire_and_forget_create_task_in_app_code():
    # The event loop keeps only weak references to tasks; a discarded result can be
    # garbage-collected mid-execution. Use spawn_background_task() instead.
    offenders = []
    for path in sorted((BACKEND_ROOT / "routers").glob("*.py")) + sorted(
        (BACKEND_ROOT / "services").rglob("*.py")
    ):
        offenders += [f"{path.relative_to(BACKEND_ROOT)}:{line}" for line in _discarded_task_calls(path)]

    assert offenders == []
