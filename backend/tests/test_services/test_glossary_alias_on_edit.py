"""Editing a glossary translation must remember the old rendering as an alias so
'Sync to Chapters' can rewrite it, including case-only corrections."""
from database import Chapter, GlobalSetting, LorebookEntry, Thread
from routers.lorebook import LorebookCreate, update_lorebook_entry
from routers.threads import reapply_glossary_thread
from services.glossary_lock import (
    append_replaced_alias,
    apply_glossary_lock,
    build_glossary_lock_rules,
)


def test_append_alias_creates_alias_line():
    assert append_replaced_alias("MALE — Protagonist", "Vennie", "Winnie") == (
        "MALE — Protagonist\nAlias: Vennie"
    )


def test_append_alias_extends_existing_line_without_duplicates():
    notes = "Protagonist\nAlias: Venni"
    once = append_replaced_alias(notes, "Vennie", "Winnie")
    assert once == "Protagonist\nAlias: Venni, Vennie"
    assert append_replaced_alias(once, "Vennie", "Winnie") == once


def test_append_alias_handles_empty_notes():
    assert append_replaced_alias(None, "Vennie", "Winnie") == "Alias: Vennie"


def test_append_alias_ignores_unchanged_empty_or_hanzi_terms():
    assert append_replaced_alias("n", "Winnie", "Winnie") == "n"
    assert append_replaced_alias("n", "", "Winnie") == "n"
    assert append_replaced_alias("n", "  ", "Winnie") == "n"
    assert append_replaced_alias("n", "文尼", "Winnie") == "n"


def test_case_only_correction_is_rewritten_by_lock():
    entry = LorebookEntry(
        original_term="文尼·法叙莉丝",
        translated_term="Winnie Varelis",
        notes=append_replaced_alias(None, "Winnie varelis", "Winnie Varelis"),
    )
    rules = build_glossary_lock_rules([entry])
    assert apply_glossary_lock("Winnie varelis menang.", rules) == "Winnie Varelis menang."
    assert apply_glossary_lock("Winnie Varelis menang.", rules) == "Winnie Varelis menang."


def test_editing_translation_then_sync_rewrites_chapters(db_session):
    db_session.add_all([
        GlobalSetting(target_language="Indonesian"),
        Thread(id=1, title="T"),
        Chapter(
            id=1, thread_id=1, order=1,
            title_translated="Vennie masuk",
            content_original="文尼来了。",
            content_translated="Vennie tersenyum. Vennie pergi.",
        ),
        LorebookEntry(id=1, thread_id=1, original_term="文尼", translated_term="Vennie",
                      notes="MALE — Protagonist"),
    ])
    db_session.commit()

    updated = update_lorebook_entry(
        1,
        LorebookCreate(original_term="文尼", translated_term="Winnie", notes="MALE — Protagonist"),
        db=db_session,
    )
    assert "Alias: Vennie" in updated.notes

    reapply_glossary_thread(1, db=db_session)
    ch = db_session.get(Chapter, 1)
    assert ch.content_translated == "Winnie tersenyum. Winnie pergi."
    assert ch.title_translated == "Winnie masuk"


def test_editing_notes_only_does_not_add_alias(db_session):
    db_session.add_all([
        Thread(id=1, title="T"),
        LorebookEntry(id=1, thread_id=1, original_term="文尼", translated_term="Winnie", notes="a"),
    ])
    db_session.commit()
    updated = update_lorebook_entry(
        1, LorebookCreate(original_term="文尼", translated_term="Winnie", notes="b"), db=db_session
    )
    assert updated.notes == "b"
