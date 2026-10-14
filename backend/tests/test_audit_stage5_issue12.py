import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Thread, Chapter, LorebookEntry, GlobalSetting
from services.context_engine import ContextEngine
from services.background_translator import (
    get_workspace_translation_lock,
    get_thread_glossary_lock,
)


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed basic thread
    t = Thread(id=1, original_title="Test Novel", title="Test Novel")
    session.add(t)
    session.commit()

    yield session
    session.close()


def test_term_matches_text_variants():
    assert ContextEngine._term_matches_text("宁凡", "宁凡走出了洞府。")
    assert ContextEngine._term_matches_text("夏茵 / 夏恩", "夏恩微笑着转过身。")
    assert ContextEngine._term_matches_text("夏茵 (女主)", "夏茵静静地看着他。")
    assert not ContextEngine._term_matches_text("李四", "宁凡走出了洞府。")
    assert not ContextEngine._term_matches_text("", "Some text")
    assert not ContextEngine._term_matches_text("宁凡", "")


def test_build_translation_prompt_no_starvation(test_db):
    # Add an entry with 0 usage that appears in chapter text
    entry_appearing = LorebookEntry(
        thread_id=1,
        original_term="金丹期",
        translated_term="Golden Core Stage",
        usage_count=0,
        is_locked=0,
    )
    # Add 10 entries with high usage that DO NOT appear in text
    for i in range(10):
        test_db.add(
            LorebookEntry(
                thread_id=1,
                original_term=f"UnrelatedTerm{i}",
                translated_term=f"Desc{i}",
                usage_count=100 - i,
                is_locked=0,
            )
        )
    test_db.add(entry_appearing)
    test_db.commit()

    # Request prompt with limit=5
    chapter_text = "他终于突破到了金丹期，气息磅礴。"
    prompt = ContextEngine.build_translation_prompt(
        test_db, thread_id=1, target_lang="English", limit=5, original_text=chapter_text
    )

    # The appearing entry MUST be present in the prompt despite low initial usage_count
    assert "Golden Core Stage" in prompt
    # Its usage count should now be incremented
    test_db.refresh(entry_appearing)
    assert entry_appearing.usage_count == 1


def test_auto_save_glossary_revalidates_after_stripping_parentheses(test_db):
    # Raw glossary payload containing an untranslated term in parentheses or invalid translation
    glossary_data = {
        "宁凡": "宁凡 (MALE — Protagonist)",  # translated_term is Chinese/untranslated
        "飞剑": "Flying Sword (WEAPON)",     # valid translated term
    }

    ContextEngine.auto_save_glossary(test_db, thread_id=1, glossary_data=glossary_data, chapter_index=1)

    saved_terms = [e.original_term for e in test_db.query(LorebookEntry).filter_by(thread_id=1).all()]
    assert "飞剑" in saved_terms
    # "宁凡" should have been rejected by is_garbage_lorebook_entry post-split
    assert "宁凡" not in saved_terms


def test_workspace_and_thread_locks_isolation():
    lock_main = get_workspace_translation_lock("main")
    lock_ghost = get_workspace_translation_lock("ghost")
    assert lock_main is not lock_ghost

    th_lock_main = get_thread_glossary_lock("main", 1)
    th_lock_ghost = get_thread_glossary_lock("ghost", 1)
    assert th_lock_main is not th_lock_ghost
