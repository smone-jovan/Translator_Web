import os

os.environ.setdefault("ALLOWED_HOSTS", "testserver,test")  # Host default TestClient & ASGITransport
import sys
import os

# Ensure backend root is on sys.path so imports like `database`, `services` resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ipaddress
import socket

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, GlobalSetting, Chapter, Thread, UserBookmark


_REAL_GETADDRINFO = socket.getaddrinfo
_FAKE_PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True, scope="session")
def isolated_module_databases(tmp_path_factory):
    """
    database.py binds app.db / ghost.db relative to the working directory, and the backend runs
    with cwd=backend, so running pytest from there would migrate and write the real library.
    Rebind the module-level engines (used by init_db) and sessionmakers (shared by every module
    that imported them) to throwaway files for the whole session.
    """
    import database

    tmp_dir = tmp_path_factory.mktemp("module_databases")
    engines = {
        name: create_engine(
            f"sqlite:///{tmp_dir / f'{name}.db'}",
            connect_args={"check_same_thread": False, "timeout": 60},
        )
        for name in ("main", "ghost")
    }
    original_engines = (database.engine_main, database.engine_ghost)

    database.engine_main, database.engine_ghost = engines["main"], engines["ghost"]
    database.SessionLocalMain.configure(bind=engines["main"])
    database.SessionLocalGhost.configure(bind=engines["ghost"])
    # Create the schema up front, as app startup does, so no test depends on an earlier one
    # having run the lifespan (or on tables left behind in a developer's real database).
    database.init_db("all")
    yield
    database.SessionLocalMain.configure(bind=original_engines[0])
    database.SessionLocalGhost.configure(bind=original_engines[1])
    database.engine_main, database.engine_ghost = original_engines
    for engine in engines.values():
        engine.dispose()


@pytest.fixture(autouse=True)
def isolated_secrets_file(monkeypatch, tmp_path):
    """save_secrets() rewrites backend/.env, which holds the developer's real API keys."""
    from services.ai import secrets

    monkeypatch.setattr(secrets, "ENV_FILE_PATH", str(tmp_path / ".env"))


@pytest.fixture(autouse=True)
def isolated_launcher_log(monkeypatch, tmp_path):
    """launcher.log() appends to the repo's real launcher.log; only matters once a test imported it."""
    launcher = sys.modules.get("launcher")
    if launcher is not None:
        monkeypatch.setattr(launcher, "LOG_FILE", str(tmp_path / "launcher.log"))


@pytest.fixture(autouse=True)
def hermetic_dns(monkeypatch):
    """
    Keep the suite offline-safe: validate_external_url() resolves hostnames before any
    (mocked) HTTP call, so unit tests used to fail without internet. Hostnames resolve to a
    fixed public IP; IP literals and localhost keep real behaviour. Tests that need a specific
    resolution still monkeypatch socket.getaddrinfo themselves, which overrides this.
    """
    def fake_getaddrinfo(host, port, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else host
        if not name or name == "localhost":
            return _REAL_GETADDRINFO(host, port, *args, **kwargs)
        try:
            ipaddress.ip_address(name)
            return _REAL_GETADDRINFO(host, port, *args, **kwargs)
        except ValueError:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_FAKE_PUBLIC_IP, port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


@pytest.fixture(autouse=True)
def isolated_adaptive_store(monkeypatch, tmp_path):
    """
    AdaptiveDOM auto-saves selector signatures per workspace: main to the git-tracked
    backend/data/adaptive_selectors.json, ghost to backend/data/adaptive_selectors.ghost.json.
    Point both at per-test temp files and start from an empty memory cache so tests neither
    dirty the working tree nor depend on each other's learned signatures.
    """
    from services.scrapers import adaptive_dom

    store_dir = tmp_path / "adaptive_store"
    monkeypatch.setattr(adaptive_dom, "_DEFAULT_STORE_PATH", store_dir / "adaptive_selectors.json")
    monkeypatch.setattr(adaptive_dom, "_GHOST_STORE_PATH", store_dir / "adaptive_selectors.ghost.json")
    monkeypatch.setattr(adaptive_dom, "_SIGNATURE_MEMORY_CACHE", {})


@pytest.fixture(autouse=True)
def isolated_on_demand_scrape_cooldown(monkeypatch):
    """
    Failed on-demand scrapes put (workspace, chapter_id) into a module-level cooldown registry.
    In-memory test databases reuse chapter ids, so start every test from an empty registry or a
    failure in one test would silently block the same chapter id in the next.
    """
    import routers.threads as threads_router

    monkeypatch.setattr(threads_router, "_failed_chapter_scrapes", {})


_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_PROXY_ENV_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """
    Fail closed: hermetic_dns maps hostnames to a real public IP, so a test whose HTTP mock
    does not take effect would otherwise reach the internet. Any non-loopback TCP connect
    raises instead; proxy variables are dropped so traffic cannot tunnel via a local proxy.
    """
    for var in _PROXY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    def _guard(addr):
        if isinstance(addr, tuple) and addr:
            try:
                ip = ipaddress.ip_address(str(addr[0]).split("%")[0])
            except ValueError:
                return
            if not ip.is_loopback:
                raise OSError(f"[test guard] external network access blocked: {addr!r}")

    def guarded_connect(self, addr):
        _guard(addr)
        return _REAL_CONNECT(self, addr)

    def guarded_connect_ex(self, addr):
        _guard(addr)
        return _REAL_CONNECT_EX(self, addr)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


@pytest.fixture
def db_session():
    """In-memory SQLite session for isolated testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_wal(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def default_global_settings(db_session):
    """Insert a default GlobalSetting row and return it."""
    gs = GlobalSetting(
        llm_provider="lm_studio",
        lm_url="http://localhost:1234",
        lm_model="qwen2.5-7b-instruct",
        target_language="Indonesian",
        openai_model="gpt-4o",
        gemini_model="gemini-2.5-flash",
        openai_url="https://api.openai.com/v1",
    )
    db_session.add(gs)
    db_session.commit()
    db_session.refresh(gs)
    return gs
