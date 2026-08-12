import sys
import os

# Ensure backend root is on sys.path so imports like `database`, `services` resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, GlobalSetting, Chapter, Thread, UserBookmark


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
