"""Test rule gender wajib pada glossary extraction prompt.

Plan: docs/ideas/gender-aware-glossary.md — Step 2.
Kontrak output untuk parser (Step 3): parenthetical PERSON entry diawali
token tepat 'MALE — ' atau 'FEMALE — ' (kata, spasi, em-dash, spasi).
Gender ditandai HANYA bila teks sumber memberi bukti; bila ragu → omit.
"""
import re

from services.prompt_templates import build_glossary_extraction_prompt


def _prompt() -> str:
    return build_glossary_extraction_prompt("English")


def test_prompt_contains_mandatory_gender_rule():
    """(a) Prompt memuat rule wajib gender untuk PERSON entry."""
    prompt = _prompt()
    assert "GENDER TOKEN" in prompt, "rule GENDER TOKEN tidak ada di prompt"
    assert "PERSON ENTRIES ONLY" in prompt, "scoping PERSON ENTRIES ONLY tidak ada"
    assert "MUST begin with the exact token" in prompt, \
        "kalimat kontrak 'MUST begin with the exact token' tidak ada"


def test_prompt_documents_gender_token_format():
    """(b) Format token 'MALE — ' / 'FEMALE — ' terdokumentasi eksak."""
    prompt = _prompt()
    # \bMALE tidak boleh match di dalam FEMALE → bukti token MALE sendiri ada
    assert re.search(r"\bMALE — ", prompt), "token 'MALE — ' tidak terdokumentasi"
    assert "FEMALE — " in prompt, "token 'FEMALE — ' tidak terdokumentasi"
    # urutan eksak: kata, spasi, em-dash, spasi
    assert "'MALE — ' or 'FEMALE — '" in prompt, \
        "pasangan token eksak 'MALE — ' or 'FEMALE — ' tidak ada"
    # contoh GOOD person entry memakai token
    assert "宁凡 → Ning Fan (MALE — " in prompt, \
        "contoh GOOD person entry tidak memuat token gender"


def test_prompt_gender_only_when_evident():
    """(c) Evidence-only: tandai gender HANYA bila bukti jelas; omit bila ragu."""
    prompt = _prompt()
    assert "ONLY when the source Chinese text makes it clear" in prompt, \
        "instruksi evidence-only tidak ada"
    assert "If uncertain, OMIT the token entirely" in prompt, \
        "instruksi omit bila ragu tidak ada"
    assert "NEVER guess from name morphology" in prompt, \
        "larangan menebak gender dari nama tidak ada"


def test_prompt_gender_scoped_to_person_entries_only():
    """(d) Person-only: entry non-person dilarang membawa token gender."""
    prompt = _prompt()
    assert "NON-PERSON entries" in prompt, "larangan non-person tidak ada"
    assert "MUST NOT carry a gender token" in prompt, \
        "kalimat 'MUST NOT carry a gender token' tidak ada"
    # contoh GOOD non-person tetap TANPA token gender
    assert "Heavenly Cloud Sect (Rival sect" in prompt
    assert not re.search(
        r"天云宗 → Heavenly Cloud Sect \((MALE|FEMALE)", prompt
    ), "contoh non-person tidak boleh membawa token gender"


def test_prompt_keeps_existing_invariants():
    """(e) Invariant lama tetap utuh: header, CONTEXT IS REQUIRED, no trailing period."""
    prompt = _prompt()
    assert "### TRANSLATOR NOTES:" in prompt, "header TRANSLATOR NOTES hilang"
    assert "CONTEXT IS REQUIRED" in prompt, "rule CONTEXT IS REQUIRED hilang"
    assert "NO trailing period" in prompt, "rule no-trailing-period hilang"
    # rule bahasa target_lang masih ter-inpolasi
    assert "English" in prompt, "aturan bahasa target_lang hilang"


def test_prompt_has_bad_example_for_guessing_gender():
    """Contoh BAD untuk menebak gender dari nama ada di prompt."""
    prompt = _prompt()
    assert "GUESSED FROM NAME" in prompt, \
        "contoh BAD menebak gender dari nama tidak ada"


def test_gender_token_always_english_even_for_other_target_lang():
    """Token gender tidak boleh ikut diterjemahkan saat target_lang bukan English."""
    prompt = build_glossary_extraction_prompt("Indonesian")
    assert "'MALE' or 'FEMALE'" in prompt and "NEVER translate or localize" in prompt, \
        "klausula token-English-always tidak ada"
    assert "MALE — " in prompt and "FEMALE — " in prompt, \
        "token bahasa Inggris hilang pada prompt bahasa Indonesia"


def test_good_example_parseable_by_parser_regex():
    """Kontrak Step 3: regex ^(MALE|FEMALE) — (dengan em-dash) match contoh GOOD."""
    prompt = _prompt()
    line = next(l for l in prompt.splitlines() if l.startswith("- 宁凡"))
    paren = line[line.index("(") + 1:]
    assert re.match(r"^(MALE|FEMALE) — ", paren), \
        "contoh GOOD person entry tidak parseable oleh parser Step 3"
