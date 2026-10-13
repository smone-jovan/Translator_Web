"""Test parse token gender di ContextEngine.auto_save_glossary.

Plan: docs/ideas/gender-aware-glossary.md — Step 3.

Kontrak (Step 2): entry PERSON boleh membawa parenthetical yang diawali token
persis `MALE — ` / `FEMALE — ` (kata, spasi, em-dash U+2014, spasi), mis.
`(MALE — Protagonist, ...)`. auto_save_glossary harus:
- menyimpan gender kanonik "MALE"/"FEMALE" (None bila token absen),
- MENYIMPAN token di notes apa adanya (tanpa stripping),
- mengisi gender entri BARU,
- backfill gender entri EXISTING yang masih NULL tanpa menyentuh field lain,
- TIDAK PERNAH menimpa gender yang sudah terisi.
"""
from unittest.mock import MagicMock

import pytest

from database import LorebookEntry
from services.context_engine import ContextEngine

THREAD_ID = 99


def _ai_output(term_line: str) -> str:
    return (
        "Full translated story here.\n\n"
        "### TRANSLATOR NOTES:\n"
        f"{term_line}\n"
    )


def _make_db(existing=None):
    """Mock db Session mengikuti pola
    test_services/test_context_engine.py::test_auto_save_glossary_splits_slash_terms."""
    db = MagicMock()
    mock_gs = MagicMock()
    mock_gs.max_context_terms = 50
    db.execute.return_value.scalar_one_or_none.return_value = mock_gs
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.execute.return_value.scalars.return_value.first.return_value = existing

    added = []
    db.add.side_effect = lambda obj: added.append(obj)
    return db, added


def _existing_entry(gender, translated_term="Old Translation", notes="Old Notes"):
    return LorebookEntry(
        thread_id=THREAD_ID,
        original_term="杰夫",
        translated_term=translated_term,
        notes=notes,
        gender=gender,
    )


def test_new_entry_with_male_token_stores_gender():
    """(a) Enri baru dengan `(MALE — ...)` menyimpan gender == "MALE"."""
    db, added = _make_db(existing=None)
    ContextEngine.auto_save_glossary(
        db,
        thread_id=THREAD_ID,
        full_text=_ai_output("- 杰夫 → Jeff (MALE — Protagonist, rivals with 王林)"),
    )

    assert len(added) == 1
    assert added[0].gender == "MALE"
    assert added[0].original_term == "杰夫"
    assert added[0].translated_term == "Jeff"


def test_new_entry_with_female_token_stores_gender():
    """(b) Enri baru dengan `(FEMALE — ...)` menyimpan gender == "FEMALE"."""
    db, added = _make_db(existing=None)
    ContextEngine.auto_save_glossary(
        db,
        thread_id=THREAD_ID,
        full_text=_ai_output("- 艾米 → Amy (FEMALE — Resistance member, allies with 杰夫)"),
    )

    assert len(added) == 1
    assert added[0].gender == "FEMALE"


def test_gender_token_is_case_insensitive():
    """(c) Drift huruf kecil `(male — ...)` tetap terekstrak sebagai "MALE"."""
    db, added = _make_db(existing=None)
    ContextEngine.auto_save_glossary(
        db,
        thread_id=THREAD_ID,
        full_text=_ai_output("- 杰夫 → Jeff (male — Protagonist, hotheaded)"),
    )

    assert len(added) == 1
    assert added[0].gender == "MALE"


def test_missing_token_leaves_gender_none():
    """(d) Parenthetical tanpa token gender → gender tetap None."""
    db, added = _make_db(existing=None)
    ContextEngine.auto_save_glossary(
        db,
        thread_id=THREAD_ID,
        full_text=_ai_output("- 杰夫 → Jeff (Protagonist of the story)"),
    )

    assert len(added) == 1
    assert added[0].gender is None


def test_existing_null_gender_is_backfilled_without_touching_other_fields(
    monkeypatch,
):
    """(e) Entry existing gender NULL + re-extract → gender terisi,
    translated_term/notes tidak berubah, tidak ada entri duplikat, tetap di-commit,
    dan enforce_context_limit TIDAK berjalan (update-only bukan new-entry)."""
    monkeypatch.setattr(
        ContextEngine,
        "enforce_context_limit",
        lambda *a, **k: pytest.fail(
            "enforce_context_limit must not run for update-only commits"
        ),
    )
    existing = _existing_entry(gender=None)
    db, added = _make_db(existing=existing)
    ContextEngine.auto_save_glossary(
        db,
        thread_id=THREAD_ID,
        full_text=_ai_output("- 杰夫 → Jeff (MALE — Protagonist, calm strategist)"),
    )

    assert existing.gender == "MALE"
    assert existing.translated_term == "Old Translation"
    assert existing.notes == "Old Notes"
    assert added == []
    db.commit.assert_called()


def test_existing_gender_is_never_overwritten():
    """(f) Entry existing gender sudah "FEMALE" + token `MALE —` → TIDAK ditimpa."""
    existing = _existing_entry(gender="FEMALE")
    db, added = _make_db(existing=existing)
    ContextEngine.auto_save_glossary(
        db,
        thread_id=THREAD_ID,
        full_text=_ai_output("- 杰夫 → Jeff (MALE — Protagonist, calm strategist)"),
    )

    assert existing.gender == "FEMALE"
    assert added == []
    db.commit.assert_not_called()


def test_gender_token_is_kept_in_notes():
    """(g) Token gender tetap ada di notes (tanpa stripping)."""
    db, added = _make_db(existing=None)
    ContextEngine.auto_save_glossary(
        db,
        thread_id=THREAD_ID,
        full_text=_ai_output("- 杰夫 → Jeff (MALE — Protagonist, rivals with 王林)"),
    )

    assert len(added) == 1
    assert "MALE — Protagonist, rivals with 王林" in added[0].notes
    assert added[0].notes.endswith("(Auto-extracted)")
