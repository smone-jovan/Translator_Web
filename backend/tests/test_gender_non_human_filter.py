"""Test filter dan guardrail entitas non-manusia untuk gender.

Memastikan hanya nama manusia (tokoh/karakter) yang boleh memiliki gender di database
dan disuntikkan ke context prompt. Nama kota, wilayah, sekte, jurus, teknik, senjata,
benda, dan entitas genderless lainnya DILARANG membawa gender atau memicu aturan pronoun.
"""
from unittest.mock import MagicMock
import pytest

from database import LorebookEntry
from services.context_engine import ContextEngine


# ---------------------------------------------------------------------------
# 1. Unit Test ContextEngine.is_non_human_term
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("orig,trans,notes,expected_non_human", [
    # Kota dan Wilayah -> Non-human (True)
    ("北京", "Beijing City", "Capital city of China", True),
    ("长安", "Chang'an", "Ancient capital city in the north", True),
    ("天南", "Tiannan Region", "A remote southern region", True),
    ("中州", "Central Continent", "Vast continent in the mortal realm", True),
    ("黑风山", "Black Wind Mountain", "Mountain where bandits reside", True),
    ("九重天", "Nine Heavens Realm", "Higher realm of existence", True),
    ("青木镇", "Greenwood Town", "A small mortal town", True),

    # Sekte dan Organisasi -> Non-human (True)
    ("天云宗", "Heavenly Cloud Sect", "A powerful righteous sect", True),
    ("血煞门", "Blood Demon Gate", "An evil demonic faction", True),
    ("神农帮", "Divine Farmer Gang", "A minor guild of herbalists", True),
    ("天机阁", "Heavenly Secret Pavilion", "Information gathering organization", True),

    # Senjata, Benda, Pil, dan Teknik -> Non-human (True)
    ("破天剑", "Heaven-Splitting Sword", "Ancient artifact sword", True),
    ("屠龙刀", "Dragon Slaying Saber", "Heavy mythical blade", True),
    ("筑基丹", "Foundation Building Pill", "Pill required to breakthrough", True),
    ("九阳神功", "Nine Yang Divine Technique", "High-tier cultivation manual", True),
    ("诛仙阵", "Immortal Slaying Array", "Lethal ancient killing formation", True),

    # Tokoh Manusia / Karakter -> Human (False)
    ("宁凡", "Ning Fan", "Protagonist, a reincarnated cultivator", False),
    ("苏婉", "Su Wan", "Female disciple of the Ice Sect", False),
    ("王林", "Wang Lin", "Ruthless young master", False),
    ("韩立", "Han Li", "Cautious cultivator who brews pills", False),
    ("张城主", "City Lord Zhang", "Lord of Beijing City", False),
    ("李宗主", "Sect Master Li", "Leader of the Heavenly Cloud Sect", False),
    ("剑圣叶", "Sword Saint Ye", "Elder who mastered the sword", False),
    ("小红", "Xiao Hong", "Maid of the princess", False),
])
def test_is_non_human_term_classification(orig, trans, notes, expected_non_human):
    result = ContextEngine.is_non_human_term(orig, trans, notes)
    assert result == expected_non_human, f"Expected {expected_non_human} for {orig}/{trans}/{notes}, got {result}"


# ---------------------------------------------------------------------------
# 2. Context Prompt Injection: Non-human entities NEVER inject gender
# ---------------------------------------------------------------------------

class MockGlobalSetting:
    def __init__(self):
        self.global_context = ""
        self.max_context_terms = 50


class MockThread:
    def __init__(self):
        self.thread_context = ""
        self.genres = ""
        self.tags = ""
        self.style_guide = ""


class MockLorebookEntry:
    def __init__(self, original_term, translated_term, notes="", gender=None):
        self.original_term = original_term
        self.translated_term = translated_term
        self.notes = notes
        self.gender = gender
        self.usage_count = 0
        self.is_archived = False


def _build_prompt_with_entries(entries):
    db = MagicMock()
    gs = MockGlobalSetting()
    thread = MockThread()

    def execute_side_effect(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt).lower()
        if "global_settings" in stmt_str:
            mock_result.scalar_one_or_none.return_value = gs
        elif "threads" in stmt_str:
            mock_result.scalar_one_or_none.return_value = thread
        elif "lorebook_entries" in stmt_str:
            mock_result.scalars().all.return_value = entries
        return mock_result

    db.execute.side_effect = execute_side_effect
    return ContextEngine.build_translation_prompt(
        db,
        thread_id=1,
        target_lang="English",
        original_text=None,
        translation_mode="quality",
    )


def test_city_with_gender_in_db_is_sanitized_in_prompt():
    """Bahkan jika baris database untuk kota memiliki gender='MALE', prompt TIDAK menyertakannya."""
    city_entry = MockLorebookEntry(
        original_term="北京",
        translated_term="Beijing City",
        notes="Capital of the Great Tang Empire",
        gender="MALE",  # Anomali DB yang salah
    )
    prompt = _build_prompt_with_entries([city_entry])

    # Baris glossary TIDAK boleh memuat token MALE
    assert "Beijing City (Capital of the Great Tang Empire)" in prompt
    assert "(MALE" not in prompt
    # Blok pronoun TIDAK boleh terpancing oleh kota
    assert "[PRONOUN / GENDER RULES - MANDATORY]" not in prompt


def test_sect_with_gender_in_db_is_sanitized_in_prompt():
    """Sekte dengan gender='FEMALE' di DB tidak memicu pronoun she/her."""
    sect_entry = MockLorebookEntry(
        original_term="天云宗",
        translated_term="Heavenly Cloud Sect",
        notes="A prominent sect",
        gender="FEMALE",  # Anomali DB
    )
    prompt = _build_prompt_with_entries([sect_entry])

    assert "Heavenly Cloud Sect (A prominent sect)" in prompt
    assert "(FEMALE" not in prompt
    assert "[PRONOUN / GENDER RULES - MANDATORY]" not in prompt


def test_human_character_preserves_gender_in_prompt():
    """Karakter manusia tetap mendapatkan token gender dan blok pronoun."""
    human_entry = MockLorebookEntry(
        original_term="宁凡",
        translated_term="Ning Fan",
        notes="Protagonist of the novel",
        gender="MALE",
    )
    prompt = _build_prompt_with_entries([human_entry])

    assert "Ning Fan (MALE — Protagonist of the novel)" in prompt
    assert "[PRONOUN / GENDER RULES - MANDATORY]" in prompt


# ---------------------------------------------------------------------------
# 3. Auto-save Glossary: Rejects gender token for non-human entities
# ---------------------------------------------------------------------------

def test_auto_save_glossary_rejects_gender_for_city():
    """Jika AI keliru menyertakan token MALE pada kota, auto_save_glossary tidak menyimpannya ke kolom gender."""
    db = MagicMock()
    mock_gs = MagicMock()
    mock_gs.max_context_terms = 50
    db.execute.return_value.scalar_one_or_none.return_value = mock_gs
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.execute.return_value.scalars.return_value.first.return_value = None

    added = []
    db.add.side_effect = lambda obj: added.append(obj)

    ai_output = (
        "Story text...\n\n"
        "### TRANSLATOR NOTES:\n"
        "- 长安城 → Chang'an City (MALE — The imperial capital city)\n"
    )

    ContextEngine.auto_save_glossary(db, thread_id=1, full_text=ai_output)

    assert len(added) == 1
    assert added[0].original_term == "长安城"
    assert added[0].translated_term == "Chang'an City"
    # Kolom gender harus None karena Chang'an City adalah nama kota!
    assert added[0].gender is None
