import pytest
from services.glossary_lock import (
    extract_pinyin_aliases,
    build_glossary_lock_rules,
    apply_glossary_lock,
    GlossaryLockRule,
)

class MockLorebookEntry:
    def __init__(self, original_term: str, translated_term: str, notes: str | None = None):
        self.original_term = original_term
        self.translated_term = translated_term
        self.notes = notes


def test_extract_pinyin_aliases_multi_character():
    """Menguji ekstraksi pinyin dari nama Hanzi multi-karakter."""
    aliases = extract_pinyin_aliases("罗毅")
    assert "Luo Yi" in aliases or "Luoyi" in aliases or "luo yi" in [a.lower() for a in aliases]


def test_extract_pinyin_aliases_single_character():
    """Menguji ekstraksi pinyin dari satu karakter Hanzi."""
    aliases = extract_pinyin_aliases("丹")
    assert any(a.lower() == "dan" for a in aliases)


def test_extract_pinyin_aliases_with_slash_subterms():
    """Menguji ekstraksi jika original_term mengandung slash."""
    aliases = extract_pinyin_aliases("夏茵 / 夏恩")
    lower_aliases = [a.lower() for a in aliases]
    assert any("xiayin" in a or "xia yin" in a for a in lower_aliases)
    assert any("xiaen" in a or "xia en" in a for a in lower_aliases)


def test_apply_glossary_lock_replaces_pinyin():
    """Memastikan bahwa jika AI mengeluarkan pinyin lama, langsung dikunci ke terjemahan target."""
    entries = [MockLorebookEntry("罗毅", "Rahmat")]
    rules = build_glossary_lock_rules(entries)

    text = "Luo Yi melangkah maju dengan pedang di tangan."
    locked = apply_glossary_lock(text, rules)
    assert "Rahmat melangkah maju dengan pedang di tangan." == locked


def test_apply_glossary_lock_replaces_raw_chinese():
    """Memastikan bahwa jika karakter Hanzi bocor ke teks terjemahan, langsung dikunci ke target."""
    entries = [MockLorebookEntry("罗毅", "Rahmat")]
    rules = build_glossary_lock_rules(entries)

    text = "罗毅 melangkah maju dengan pedang di tangan."
    locked = apply_glossary_lock(text, rules)
    assert "Rahmat melangkah maju dengan pedang di tangan." == locked


def test_apply_glossary_lock_case_insensitive_multiword():
    """Memastikan nama multi-kata dicocokkan secara case-insensitive."""
    entries = [MockLorebookEntry("罗毅", "Rahmat")]
    rules = build_glossary_lock_rules(entries)

    text = "luo yi dan LUO YI keduanya adalah orang yang sama."
    locked = apply_glossary_lock(text, rules)
    assert "Rahmat dan Rahmat keduanya adalah orang yang sama." == locked


def test_apply_glossary_lock_stopword_guardrail():
    """
    KATA PENDEK (DAN):
    Jika istilah adalah '丹' (Pinyin: Dan), kata sambung bahasa Indonesia 'dan' (huruf kecil)
    TIDAK BOLEH diganti! Hanya kata kapital 'Dan' atau karakter '丹' yang diganti.
    """
    entries = [MockLorebookEntry("丹", "Pil Roh")]
    rules = build_glossary_lock_rules(entries)

    text = "Budi dan Ani mengonsumsi Dan di dalam gua."
    locked = apply_glossary_lock(text, rules)
    assert locked == "Budi dan Ani mengonsumsi Pil Roh di dalam gua."


def test_apply_glossary_lock_phrase_length_priority():
    """
    Frasa lebih panjang harus dieksekusi lebih dahulu daripada substringnya.
    'Luo Yi Chen' -> 'Rahmat Fajar'
    'Luo Yi' -> 'Rahmat'
    """
    entries = [
        MockLorebookEntry("罗毅", "Rahmat"),
        MockLorebookEntry("罗毅晨", "Rahmat Fajar"),
    ]
    rules = build_glossary_lock_rules(entries)

    text = "Luo Yi Chen menyapa Luo Yi dengan hormat."
    locked = apply_glossary_lock(text, rules)
    assert locked == "Rahmat Fajar menyapa Rahmat dengan hormat."


def test_apply_glossary_lock_idempotent():
    """Teks yang sudah menggunakan istilah target tidak boleh diubah lagi."""
    entries = [MockLorebookEntry("罗毅", "Rahmat")]
    rules = build_glossary_lock_rules(entries)

    text = "Rahmat melangkah maju dengan tenang."
    locked = apply_glossary_lock(text, rules)
    assert locked == text


def test_context_engine_enforce_glossary_locking():
    """Menguji ContextEngine.enforce_glossary_locking dengan mock Session SQLAlchemy."""
    from unittest.mock import MagicMock
    from services.context_engine import ContextEngine

    mock_db = MagicMock()
    mock_entry = MockLorebookEntry("罗毅", "Rahmat")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_entry]
    mock_db.execute.return_value = mock_result

    text = "Luo Yi menatap ke arah langit malam."
    locked = ContextEngine.enforce_glossary_locking(mock_db, thread_id=1, text=text)
    assert locked == "Rahmat menatap ke arah langit malam."


def test_context_engine_build_prompt_includes_pinyin():
    """Menguji bahwa prompt yang dibangun menyertakan petunjuk pinyin untuk karakter Hanzi."""
    from unittest.mock import MagicMock
    from services.context_engine import ContextEngine

    mock_db = MagicMock()
    mock_entry = MockLorebookEntry("罗毅", "Rahmat")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_entry]
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    prompt = ContextEngine.build_translation_prompt(mock_db, thread_id=1, target_lang="Indonesian")
    assert "罗毅 (Pinyin: Luo Yi) → Rahmat" in prompt


def test_apply_glossary_lock_no_cascading_repeats():
    """
    Memastikan istilah dengan pinyin di dalam hasil terjemahan target
    (e.g. '白蛇' -> 'Bai She (White Serpent)') TIDAK mengalami efek domino
    berantai yang melipatgandakan '(White Serpent)'.
    """
    entries = [MockLorebookEntry("白蛇", "Bai She (White Serpent)")]
    rules = build_glossary_lock_rules(entries)

    # 1. Dari teks Pinyin bahasa Inggris
    text_pinyin = "The single-eyed man known as Bai She had a slight twitch."
    res_pinyin = apply_glossary_lock(text_pinyin, rules)
    assert res_pinyin == "The single-eyed man known as Bai She (White Serpent) had a slight twitch."

    # 2. Dari teks Hanzi asli
    text_hanzi = "被唤作白蛇的独眼男子"
    res_hanzi = apply_glossary_lock(text_hanzi, rules)
    assert res_hanzi == "被唤作Bai She (White Serpent)的独眼男子"


def test_apply_glossary_lock_idempotency_self_containing():
    """
    Memastikan bahwa teks yang SUDAH memuat istilah target yang mengandung Pinyin
    (e.g. 'Bai She (White Serpent)') tidak terduplikasi menjadi berulang.
    """
    entries = [MockLorebookEntry("白蛇", "Bai She (White Serpent)")]
    rules = build_glossary_lock_rules(entries)

    text_already_translated = "What is it, Bai She (White Serpent)?"
    res = apply_glossary_lock(text_already_translated, rules)
    assert res == "What is it, Bai She (White Serpent)?"


def test_apply_glossary_lock_multiple_passes_idempotent():
    """
    Memastikan dipanggil berulang kali (zero token / mass sync berkali-kali)
    hasilnya tetap 100% konsisten tanpa penambahan string liar.
    """
    entries = [MockLorebookEntry("白蛇", "Bai She (White Serpent)")]
    rules = build_glossary_lock_rules(entries)

    text = "What is it, Bai She?"
    res = text
    for _ in range(5):
        res = apply_glossary_lock(res, rules)

    assert res == "What is it, Bai She (White Serpent)?"


