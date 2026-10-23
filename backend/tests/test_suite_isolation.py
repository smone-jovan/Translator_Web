"""Issue 25 (A-07): running the suite must never touch the developer's real secrets, databases
or launcher log. The backend runs with cwd=backend, so ./app.db there is the real library."""
import os
import sqlite3
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent

sys.path.insert(0, str(ROOT_DIR))
import launcher  # noqa: E402  (imported at collection, like test_launcher.py)


def _read(path: Path):
    return path.read_bytes() if path.exists() else None


def _has_thread_titled(db_path: Path, title: str) -> bool:
    if not db_path.exists():
        return False
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT 1 FROM threads WHERE title = ?", (title,)).fetchone() is not None
    except sqlite3.OperationalError:  # no threads table
        return False
    finally:
        conn.close()


def test_saving_secrets_never_writes_the_real_env_file():
    from services.ai.secrets import save_secrets

    real_env = BACKEND_DIR / ".env"
    before = _read(real_env)

    save_secrets(openrouter_api_key="sk-or-isolation-guard")

    assert _read(real_env) == before


def test_module_level_sessions_never_write_the_real_databases():
    import database
    from database import Thread

    marker = f"isolation-guard-{uuid.uuid4()}"
    database.init_db("all")
    for workspace in ("main", "ghost"):
        with database.get_session(workspace) as db:
            db.add(Thread(title=marker))
            db.commit()

    for directory in {Path.cwd(), BACKEND_DIR}:
        for name in ("app.db", "ghost.db"):
            assert not _has_thread_titled(directory / name, marker), directory / name


def test_launcher_log_never_appends_to_the_real_log_file():
    real_log = Path(os.path.join(str(ROOT_DIR), "launcher.log"))
    before = _read(real_log)

    launcher.log("test", "isolation-guard")

    assert _read(real_log) == before
