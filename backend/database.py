"""
Database setup — SQLite via SQLAlchemy 2.0.
Tabel: threads, chapters, lorebook_entries, translation_segments, user_bookmarks, global_settings
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import create_engine, event, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Activate WAL mode for concurrent read/write safety across multi-device sessions (ADR-008)
@event.listens_for(engine, "connect")
def _set_sqlite_wal(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class GlobalSetting(Base):
    """Global context settings and permanent config."""
    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    global_context: Mapped[Optional[str]] = mapped_column(Text)
    lm_url: Mapped[str] = mapped_column(String(500), default="http://localhost:1234")
    lm_model: Mapped[Optional[str]] = mapped_column(String(500))
    target_language: Mapped[str] = mapped_column(String(50), default="Indonesian")
    prefetch_enabled: Mapped[int] = mapped_column(default=0)  # 0 = disabled, 1 = enabled
    prefetch_count: Mapped[int] = mapped_column(default=2)    # 1-5 chapters
    prefetch_mode: Mapped[str] = mapped_column(String(20), default="soft") # soft or hard
    polish_mode: Mapped[str] = mapped_column(String(20), default="soft") # soft or hard
    polish_soft_limit: Mapped[int] = mapped_column(default=100) # 50-150 titles
    max_context_terms: Mapped[int] = mapped_column(default=150) # 20, 50, 100, 200, 300, 500, 750, 1000
    extract_chapter_count: Mapped[int] = mapped_column(default=25)
    extract_sample_size: Mapped[int] = mapped_column(default=1000)
    always_hide_thoughts: Mapped[int] = mapped_column(default=1) # 0 = disabled, 1 = enabled
    chapter_token_cap_enabled: Mapped[int] = mapped_column(default=1) # 0 = disabled, 1 = enabled
    chapter_token_cap: Mapped[int] = mapped_column(default=22000)
    
    # Cloud & Provider settings (ADR-029)
    llm_provider: Mapped[str] = mapped_column(String(50), default="lm_studio")
    openai_url: Mapped[str] = mapped_column(String(500), default="https://api.openai.com/v1")
    openai_model: Mapped[str] = mapped_column(String(200), default="gpt-4o")
    gemini_model: Mapped[str] = mapped_column(String(200), default="gemini-2.5-flash")
    openai_api_key: Mapped[Optional[str]] = mapped_column(String(500), default="")
    gemini_api_key: Mapped[Optional[str]] = mapped_column(String(500), default="")


class Thread(Base):
    """Satu thread = satu buku/proyek terjemahan."""
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20), default="url")
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    cover_image: Mapped[Optional[str]] = mapped_column(Text)
    original_title: Mapped[Optional[str]] = mapped_column(String(500))
    genres: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(String(100))
    status_coo: Mapped[Optional[str]] = mapped_column(String(200))
    synopsis: Mapped[Optional[str]] = mapped_column(Text)
    thread_context: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    chapters: Mapped[List["Chapter"]] = relationship(back_populates="thread", cascade="all, delete")
    lorebook: Mapped[List["LorebookEntry"]] = relationship(back_populates="thread", cascade="all, delete")
    bookmarks: Mapped[List["UserBookmark"]] = relationship(back_populates="thread", cascade="all, delete")
    relationships: Mapped[List["CharacterRelationship"]] = relationship(back_populates="thread", cascade="all, delete")


class Chapter(Base):
    """Satu chapter dari sebuah thread."""
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), nullable=False)
    order: Mapped[int] = mapped_column(default=0)
    title_original: Mapped[Optional[str]] = mapped_column(String(500))
    title_translated: Mapped[Optional[str]] = mapped_column(String(500))
    content_original: Mapped[Optional[str]] = mapped_column(Text)
    content_translated: Mapped[Optional[str]] = mapped_column(Text)
    translation_status: Mapped[str] = mapped_column(String(20), default="idle")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    thread: Mapped["Thread"] = relationship(back_populates="chapters")
    segments: Mapped[List["TranslationSegment"]] = relationship(back_populates="chapter", cascade="all, delete")


class TranslationSegment(Base):
    """Satu paragraf/kalimat terjemahan."""
    __tablename__ = "translation_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    order: Mapped[int] = mapped_column(default=0)
    original_text: Mapped[Optional[str]] = mapped_column(Text)
    translated_text: Mapped[Optional[str]] = mapped_column(Text)
    display_mode: Mapped[str] = mapped_column(String(20), default="translated")

    chapter: Mapped["Chapter"] = relationship(back_populates="segments")


class UserBookmark(Base):
    """Menyimpan history baca terakhir."""
    __tablename__ = "user_bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    scroll_progress: Mapped[float] = mapped_column(default=0.0)
    last_read_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    thread: Mapped["Thread"] = relationship(back_populates="bookmarks")


class CharacterRelationship(Base):
    """Menyimpan koneksi antar karakter (misal dari Lorebook) dalam satu thread."""
    __tablename__ = "character_relationships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), nullable=False)
    source_term: Mapped[str] = mapped_column(String(200), nullable=False)
    target_term: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100)) # e.g., "Friend", "Enemy", "Master"
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    thread: Mapped["Thread"] = relationship(back_populates="relationships")


class LorebookEntry(Base):
    """Term/nama yang harus dijaga konsistensinya."""
    __tablename__ = "lorebook_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), nullable=False)
    original_term: Mapped[str] = mapped_column(String(200), nullable=False)
    translated_term: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    usage_count: Mapped[int] = mapped_column(default=0)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    is_locked: Mapped[bool] = mapped_column(default=False)
    is_archived: Mapped[bool] = mapped_column(default=False)

    thread: Mapped["Thread"] = relationship(back_populates="lorebook")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Auto-migration: check for missing columns in global_settings, lorebook_entries, and threads
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    columns_gs = [c['name'] for c in inspector.get_columns('global_settings')]
    columns_lb = [c['name'] for c in inspector.get_columns('lorebook_entries')]
    columns_th = [c['name'] for c in inspector.get_columns('threads')]
    columns_ub = [c['name'] for c in inspector.get_columns('user_bookmarks')]

    # Ensure character_relationships table exists (it gets created by create_all, but just to be safe with migrations)

    with engine.connect() as conn:
        if 'author' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'author' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN author VARCHAR(200)"))
            conn.commit()

        if 'cover_image' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'cover_image' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN cover_image TEXT"))
            conn.commit()
            
        if 'original_title' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'original_title' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN original_title VARCHAR(500)"))
            conn.commit()

        if 'genres' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'genres' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN genres TEXT"))
            conn.commit()

        if 'tags' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'tags' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN tags TEXT"))
            conn.commit()

        if 'status' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'status' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN status VARCHAR(100)"))
            conn.commit()

        if 'status_coo' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'status_coo' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN status_coo VARCHAR(200)"))
            conn.commit()

        if 'synopsis' not in columns_th:
            print("[MIGRASI] Menambahkan kolom 'synopsis' ke dalam tabel threads...")
            conn.execute(text("ALTER TABLE threads ADD COLUMN synopsis TEXT"))
            conn.commit()
            
        if 'prefetch_count' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'prefetch_count' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN prefetch_count INTEGER DEFAULT 2"))
            conn.commit()
            
        if 'prefetch_mode' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'prefetch_mode' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN prefetch_mode VARCHAR(20) DEFAULT 'soft'"))
            conn.commit()
            
        if 'polish_mode' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'polish_mode' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN polish_mode VARCHAR(20) DEFAULT 'soft'"))
            conn.commit()
            
        if 'polish_soft_limit' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'polish_soft_limit' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN polish_soft_limit INTEGER DEFAULT 100"))
            conn.commit()
            
        if 'max_context_terms' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'max_context_terms' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN max_context_terms INTEGER DEFAULT 50"))
            conn.commit()

        if 'extract_chapter_count' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'extract_chapter_count' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN extract_chapter_count INTEGER DEFAULT 25"))
            conn.commit()

        if 'extract_sample_size' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'extract_sample_size' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN extract_sample_size INTEGER DEFAULT 1000"))
            conn.commit()
            
        if 'llm_provider' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'llm_provider' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN llm_provider VARCHAR(50) DEFAULT 'lm_studio'"))
            conn.commit()
            
        if 'openai_url' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'openai_url' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN openai_url VARCHAR(500) DEFAULT 'https://api.openai.com/v1'"))
            conn.commit()
            
        if 'openai_model' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'openai_model' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN openai_model VARCHAR(200) DEFAULT 'gpt-4o'"))
            conn.commit()
            
        if 'gemini_model' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'gemini_model' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN gemini_model VARCHAR(200) DEFAULT 'gemini-2.5-flash'"))
            conn.commit()
            
        if 'openai_api_key' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'openai_api_key' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN openai_api_key VARCHAR(500) DEFAULT ''"))
            conn.commit()
            
        if 'gemini_api_key' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'gemini_api_key' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN gemini_api_key VARCHAR(500) DEFAULT ''"))
            conn.commit()
            
        if 'always_hide_thoughts' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'always_hide_thoughts' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN always_hide_thoughts INTEGER DEFAULT 1"))
            conn.commit()

        if 'chapter_token_cap_enabled' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'chapter_token_cap_enabled' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN chapter_token_cap_enabled INTEGER DEFAULT 1"))
            conn.commit()

        if 'chapter_token_cap' not in columns_gs:
            print("[MIGRASI] Menambahkan kolom 'chapter_token_cap' ke dalam tabel global_settings...")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN chapter_token_cap INTEGER DEFAULT 22000"))
            conn.commit()
            
        if 'is_locked' not in columns_lb:
            print("[MIGRASI] Menambahkan kolom 'is_locked' ke dalam tabel lorebook_entries...")
            conn.execute(text("ALTER TABLE lorebook_entries ADD COLUMN is_locked BOOLEAN DEFAULT FALSE"))
            conn.commit()
            
        if 'is_archived' not in columns_lb:
            print("[MIGRASI] Menambahkan kolom 'is_archived' ke dalam tabel lorebook_entries...")
            conn.execute(text("ALTER TABLE lorebook_entries ADD COLUMN is_archived BOOLEAN DEFAULT FALSE"))
            conn.commit()
            
        if 'scroll_progress' not in columns_ub:
            print("[MIGRASI] Menambahkan kolom 'scroll_progress' ke dalam tabel user_bookmarks...")
            conn.execute(text("ALTER TABLE user_bookmarks ADD COLUMN scroll_progress REAL DEFAULT 0.0"))
            conn.commit()
            
    print("[SUKSES] Inisialisasi basis data selesai - app.db siap digunakan.")
