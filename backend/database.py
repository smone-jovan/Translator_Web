"""
Database setup — SQLite via SQLAlchemy.
Tabel: threads, chapters, lorebook_entries
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

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

    id = Column(Integer, primary_key=True, index=True)
    global_context = Column(Text, nullable=True)
    lm_url = Column(String(500), default="http://localhost:1234")
    lm_model = Column(String(500), nullable=True)
    target_language = Column(String(50), default="Indonesian")


class Thread(Base):
    """Satu thread = satu buku/proyek terjemahan."""
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    source_type = Column(String(20), default="url")  # "url" | "epub"
    source_url = Column(Text, nullable=True)
    thread_context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    chapters = relationship("Chapter", back_populates="thread", cascade="all, delete")
    lorebook = relationship("LorebookEntry", back_populates="thread", cascade="all, delete")



class Chapter(Base):
    """Satu chapter dari sebuah thread (bisa dari EPUB atau URL)."""
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    order = Column(Integer, default=0)
    title_original = Column(String(500), nullable=True)
    title_translated = Column(String(500), nullable=True)
    content_original = Column(Text, nullable=True)
    content_translated = Column(Text, nullable=True)
    translation_status = Column(String(20), default="idle") # "idle", "processing", "done", "error"
    created_at = Column(DateTime, default=func.now())

    thread = relationship("Thread", back_populates="chapters")
    segments = relationship("TranslationSegment", back_populates="chapter", cascade="all, delete")


class TranslationSegment(Base):
    """Satu paragraf/kalimat untuk keperluan toggle show original/translated."""
    __tablename__ = "translation_segments"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    order = Column(Integer, default=0)
    original_text = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    display_mode = Column(String(20), default="translated") # "original", "translated", "both", "hidden"
    
    chapter = relationship("Chapter", back_populates="segments")


class LorebookEntry(Base):
    """Term/nama yang harus dijaga konsistensinya dalam terjemahan."""
    __tablename__ = "lorebook_entries"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    original_term = Column(String(200), nullable=False)
    translated_term = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    thread = relationship("Thread", back_populates="lorebook")


def get_db():
    """Dependency untuk FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Buat semua tabel jika belum ada."""
    Base.metadata.create_all(bind=engine)
