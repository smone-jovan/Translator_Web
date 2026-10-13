"""Auto-migration test untuk kolom `gender` di lorebook_entries.

Plan: docs/ideas/gender-aware-glossary.md — Step 1.
Menguji init_db() pada engine SQLite sementara (tmp_path) tanpa menyentuh
app.db / ghost.db.
"""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base, LorebookEntry, Thread


# Skema legacy lorebook_entries TANPA kolom gender (state DB lama sebelum migrasi).
LEGACY_LOREBOOK_DDL = """
CREATE TABLE lorebook_entries (
    id INTEGER NOT NULL PRIMARY KEY,
    thread_id INTEGER NOT NULL,
    original_term VARCHAR(200) NOT NULL,
    translated_term VARCHAR(200) NOT NULL,
    notes TEXT,
    usage_count INTEGER,
    last_used_at DATETIME,
    created_at DATETIME,
    is_locked BOOLEAN NOT NULL,
    is_archived BOOLEAN NOT NULL,
    FOREIGN KEY(thread_id) REFERENCES threads (id)
)
"""


@pytest.fixture
def tmp_engine(tmp_path):
    """Engine SQLite file-based sementara; di-dispose setelah test."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'migration_test.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    engine.dispose()


def _run_init_db(monkeypatch, engine):
    """Jalankan init_db() dengan engine uji menggantikan engine aktif."""
    monkeypatch.setattr(database, "_get_active_engine", lambda: engine)
    database.init_db()


def _gender_column(engine):
    cols = inspect(engine).get_columns("lorebook_entries")
    return next((c for c in cols if c["name"] == "gender"), None)


def test_gender_column_exists_after_fresh_init_db(tmp_engine, monkeypatch):
    """(a) init_db() pada DB baru menghasilkan tabel dengan kolom gender."""
    _run_init_db(monkeypatch, tmp_engine)

    col = _gender_column(tmp_engine)
    assert col is not None, "lorebook_entries.gender tidak ada setelah init_db()"


def test_gender_column_is_nullable_and_defaults_to_none(tmp_engine, monkeypatch):
    """(b) Kolom gender nullable dan row baru default-nya None."""
    _run_init_db(monkeypatch, tmp_engine)

    col = _gender_column(tmp_engine)
    assert col is not None, "lorebook_entries.gender tidak ada setelah init_db()"
    assert col["nullable"] is True, "kolom gender harus nullable"

    # Model ORM mendeklarasikan gender
    assert "gender" in LorebookEntry.__table__.columns, \
        "LorebookEntry ORM belum mendeklarasikan field gender"

    # Row baru tanpa gender harus bernilai None
    Session = sessionmaker(bind=tmp_engine)
    with Session() as session:
        thread = Thread(title="uji")
        session.add(thread)
        session.commit()

        entry = LorebookEntry(
            thread_id=thread.id,
            original_term="老王",
            translated_term="Old Wang",
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        assert entry.gender is None, "gender harus default None untuk row baru"


def test_init_db_adds_gender_to_legacy_db(tmp_engine, monkeypatch):
    """(c) DB lama tanpa kolom gender: init_db() menambahkannya tanpa error
    dan row yang sudah ada tetap NULL."""
    # Bangun skema legacy: lorebook_entries tanpa gender, tabel lain menyusul
    with tmp_engine.begin() as conn:
        conn.execute(text(LEGACY_LOREBOOK_DDL))
    Base.metadata.create_all(bind=tmp_engine)  # skip tabel yang sudah ada

    # Seed row legacy yang harus tetap NULL setelah migrasi
    with tmp_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO threads (title, source_type, created_at) "
            "VALUES ('legacy', 'url', CURRENT_TIMESTAMP)"
        ))
        thread_id = conn.execute(text("SELECT id FROM threads")).scalar()
        conn.execute(text(
            "INSERT INTO lorebook_entries "
            "(thread_id, original_term, translated_term, usage_count, "
            " is_locked, is_archived) "
            "VALUES (:tid, '老王', 'Old Wang', 3, 0, 0)"
        ), {"tid": thread_id})

    # Migrasi: tidak boleh raise
    _run_init_db(monkeypatch, tmp_engine)

    col = _gender_column(tmp_engine)
    assert col is not None, "init_db() tidak menambahkan kolom gender ke DB legacy"
    assert col["nullable"] is True, "kolom gender hasil migrasi harus nullable"

    with tmp_engine.connect() as conn:
        row = conn.execute(text(
            "SELECT gender FROM lorebook_entries WHERE original_term = '老王'"
        )).fetchone()
    assert row is not None, "row legacy harus tetap ada setelah migrasi"
    assert row[0] is None, "row legacy harus NULL pada kolom gender baru"
