"""Issue 25 (A-07): running the suite must never touch the developer's real secrets, databases
or launcher log. The backend runs with cwd=backend, so ./app.db there is the real library.

Each guard checks where a write would land *before* writing, so a regression fails the test
without damaging the real file (and cannot pass on a re-run because the damage already matches).
"""
import os
import sqlite3
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
REAL_DATABASES = {
    (directory / name).resolve()
    for directory in (Path.cwd(), BACKEND_DIR)
    for name in ("app.db", "ghost.db")
}

sys.path.insert(0, str(ROOT_DIR))
import launcher  # noqa: E402  (imported at collection, like test_launcher.py)


def _read(path: Path):
    return path.read_bytes() if path.exists() else None


def test_saving_secrets_never_writes_the_real_env_file():
    from services.ai import secrets

    real_env = (BACKEND_DIR / ".env").resolve()
    target = Path(secrets.ENV_FILE_PATH).resolve()
    assert target != real_env
    before = _read(real_env)
    key = f"sk-or-{uuid.uuid4()}"

    secrets.save_secrets(openrouter_api_key=key)

    assert key in target.read_text(encoding="utf-8")
    assert _read(real_env) == before


def test_module_level_sessions_never_write_the_real_databases():
    import database
    from database import Thread

    marker = f"isolation-guard-{uuid.uuid4()}"
    for workspace in ("main", "ghost"):
        target = Path(database.get_session_factory(workspace).kw["bind"].url.database).resolve()
        assert target not in REAL_DATABASES

        with database.get_session(workspace) as db:
            db.add(Thread(title=marker))
            db.commit()

        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        try:
            assert conn.execute("SELECT 1 FROM threads WHERE title = ?", (marker,)).fetchone()
        finally:
            conn.close()
            # The session database is shared by the whole run; leave no book behind for others.
            with database.get_session(workspace) as db:
                db.query(Thread).filter(Thread.title == marker).delete()
                db.commit()


def test_launcher_log_never_appends_to_the_real_log_file():
    real_log = Path(os.path.join(str(ROOT_DIR), "launcher.log")).resolve()
    target = Path(launcher.LOG_FILE).resolve()
    assert target != real_log
    before = _read(real_log)
    line = f"isolation-guard-{uuid.uuid4()}"

    launcher.log("test", line)

    assert line in target.read_text(encoding="utf-8")
    assert _read(real_log) == before
