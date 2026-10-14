import inspect
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database import Base, Thread, LorebookEntry, GlobalSetting
from main import app


@pytest.fixture
def stage2_db_setup(monkeypatch):
    """Isolated in-memory database setup for Stage 2 testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionTest() as db:
        gs = GlobalSetting(
            translation_mode="fast",
            max_context_terms=10,
            llm_provider="gemini",
            gemini_model="gemini-2.5-flash",
        )
        db.add(gs)

        t = Thread(title="Martial World", original_title="武极天下", source_type="manual")
        db.add(t)
        db.flush()

        # Add 2 lorebook entries
        e1 = LorebookEntry(
            thread_id=t.id,
            original_term="宋书航",
            translated_term="Song Shuhang",
            gender="MALE",
            is_locked=True,
            usage_count=5,
        )
        e2 = LorebookEntry(
            thread_id=t.id,
            original_term="方仙道",
            translated_term="Fang Xian Dao",
            gender=None,
            is_locked=False,
            usage_count=10,
        )
        db.add_all([e1, e2])
        db.commit()

    monkeypatch.setattr("database.SessionLocalMain", SessionTest)
    monkeypatch.setattr("database.SessionLocalGhost", SessionTest)
    monkeypatch.setattr("database.SessionLocal", SessionTest)
    monkeypatch.setattr("database.get_db", lambda ws=None: SessionTest())

    return SessionTest


# --------------------------------------------------------------------------
# 1. glossary_lock: Single-syllable Pinyin case-sensitivity & English collision
# --------------------------------------------------------------------------
def test_glossary_lock_single_syllable_case_sensitive():
    """
    Single-syllable pinyin with 4+ characters (e.g. 'Song', 'Fang', 'Long', 'Wang')
    must be matched case-sensitively so English common words like 'a beautiful song'
    or 'a long time' are NOT replaced by character names.
    """
    from services.glossary_lock import build_glossary_lock_rules, apply_glossary_lock
    from database import LorebookEntry

    # Single Hanzi character entry whose pinyin has 4 letters
    entry_song = LorebookEntry(
        id=1,
        thread_id=1,
        original_term="宋",
        translated_term="Song",
        is_locked=True
    )
    entry_long = LorebookEntry(
        id=2,
        thread_id=1,
        original_term="龙",
        translated_term="Dragon Long",
        is_locked=True
    )

    rules = build_glossary_lock_rules([entry_song, entry_long])

    text = "She listened to a beautiful song for a long time. Then Song arrived with Dragon Long."
    locked = apply_glossary_lock(text, rules)

    # 'song' and 'long' in lower-case English must be untouched!
    assert "a beautiful song" in locked, f"Lower-case 'song' was incorrectly replaced: {locked}"
    assert "a long time" in locked, f"Lower-case 'long' was incorrectly replaced: {locked}"
    # Capitalized 'Song' should be replaced / preserved
    assert "Then Song arrived" in locked or "Then Song arrived with Dragon Long" in locked


def test_glossary_lock_stopwords_expanded():
    """COMMON_COLLISION_STOPWORDS must include common English/Indo words that collide with pinyin."""
    from services.glossary_lock import COMMON_COLLISION_STOPWORDS
    expected_words = {"song", "fang", "long", "wang", "tang", "gang", "ring", "king", "wing", "hang", "bang", "yang", "uang", "tiang", "siang", "liar"}
    missing = expected_words - COMMON_COLLISION_STOPWORDS
    assert not missing, f"COMMON_COLLISION_STOPWORDS is missing expected collision words: {missing}"


# --------------------------------------------------------------------------
# 2. context_engine: False-negative non-human entities & is_locked priority
# --------------------------------------------------------------------------
def test_context_engine_non_human_with_master_or_protagonist_notes():
    """
    Artifacts, weapons, or skills whose description notes mention 'master' or 'protagonist'
    (e.g. 'A sacred sword forged by the sect master') must still be classified as non-human!
    """
    from services.context_engine import ContextEngine

    # Sword mentioning sect master (Romanized/English name where only notes clarify it is a weapon)
    res_sword_en = ContextEngine.is_non_human_term(
        original_term="Deathbringer",
        translated_term="Deathbringer",
        notes="A sacred sword forged by the sect master thousands of years ago."
    )
    assert res_sword_en is True, "Weapon with English name mentioning 'master' in notes was incorrectly classified as human!"

    # Sword mentioning sect master (Hanzi)
    res_sword = ContextEngine.is_non_human_term(
        original_term="天霜剑",
        translated_term="Sky Frost Sword",
        notes="A sacred sword forged by the sect master thousands of years ago."
    )
    assert res_sword is True, "Sword mentioning 'master' was incorrectly classified as human!"

    # Technique mentioning protagonist
    res_tech = ContextEngine.is_non_human_term(
        original_term="九阳真经",
        translated_term="Nine Yang Manual",
        notes="The signature technique created by the ancient patriarch and practiced by the protagonist."
    )
    assert res_tech is True, "Technique mentioning 'patriarch/protagonist' was incorrectly classified as human!"

    # Pill mentioning alchemist
    res_pill = ContextEngine.is_non_human_term(
        original_term="聚气丹",
        translated_term="Qi Gathering Pill",
        notes="A rare pill concocted by a supreme alchemist."
    )
    assert res_pill is True, "Pill mentioning 'alchemist' was incorrectly classified as human!"


def test_context_engine_orders_locked_entries_first():
    """build_translation_prompt must order by LorebookEntry.is_locked.desc() first to protect user-locked terms."""
    import services.context_engine as ce_module
    source_code = inspect.getsource(ce_module.ContextEngine.build_translation_prompt)
    assert "desc(LorebookEntry.is_locked)" in source_code or "LorebookEntry.is_locked.desc()" in source_code, (
        "build_translation_prompt must prioritize LorebookEntry.is_locked.desc() in order_by"
    )


# --------------------------------------------------------------------------
# 3. lorebook router: Duplicate term collision on PUT /api/lorebook/{id}
# --------------------------------------------------------------------------
def test_lorebook_put_rejects_duplicate_original_term(stage2_db_setup):
    """PUT /api/lorebook/{entry_id} must reject renaming to an original_term that already exists in the thread."""
    client = TestClient(app)
    # Entry 2 tries to rename its original_term to Entry 1's ('宋书航')
    response = client.put("/api/lorebook/2", json={
        "original_term": "宋书航",
        "translated_term": "Conflict Name",
    })
    # Must fail with 400 or 409 Conflict
    assert response.status_code in [400, 409], f"Expected 400/409 conflict, got {response.status_code}"
    assert "already exists" in response.json()["detail"].lower()
