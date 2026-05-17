"""
Database setup — SQLite via SQLAlchemy 2.0.
Tabel: threads, chapters, lorebook_entries, translation_segments, user_bookmarks, global_settings
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import create_engine, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
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


class Thread(Base):
    """Satu thread = satu buku/proyek terjemahan."""
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="url")
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    thread_context: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    chapters: Mapped[List["Chapter"]] = relationship(back_populates="thread", cascade="all, delete")
    lorebook: Mapped[List["LorebookEntry"]] = relationship(back_populates="thread", cascade="all, delete")
    bookmarks: Mapped[List["UserBookmark"]] = relationship(back_populates="thread", cascade="all, delete")


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
    last_read_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    thread: Mapped["Thread"] = relationship(back_populates="bookmarks")


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

    thread: Mapped["Thread"] = relationship(back_populates="lorebook")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Auto-migration: check for missing columns in global_settings
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('global_settings')]
    
    with engine.connect() as conn:
        if 'prefetch_count' not in columns:
            print("⚠️ Migrating: Adding 'prefetch_count' to global_settings")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN prefetch_count INTEGER DEFAULT 2"))
            conn.commit()
            
        if 'prefetch_mode' not in columns:
            print("⚠️ Migrating: Adding 'prefetch_mode' to global_settings")
            conn.execute(text("ALTER TABLE global_settings ADD COLUMN prefetch_mode VARCHAR(20) DEFAULT 'soft'"))
            conn.commit()
            
    print("[OK] Database initialized - app.db ready.")
