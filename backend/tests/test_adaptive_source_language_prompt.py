"""Tests for the Adaptive Source Language Prompt Engine (ADR-111).

Validates:
1. Dynamic source language detection (Korean, Chinese, Japanese).
2. Direct Korean-to-Target translation guidelines (no double-translation via Chinese).
3. Korean honorifics, zero anaphora / pronoun consistency, and hunter/system terms.
4. Korean chapter title prefix formatting and cleaning.
5. Korean glossary extraction and gender token rules.
6. Direct glossary locking for raw Korean terms.
"""
from unittest.mock import MagicMock
import pytest

from services.prompt_templates import (
    detect_source_language,
    build_core_translation_guidelines,
    build_title_translation_prompt,
    build_glossary_extraction_prompt,
    build_relationship_extraction_prompt,
)
from services.context_engine import ContextEngine
from services.glossary_lock import build_glossary_lock_rules, apply_glossary_lock
from routers.polish import clean_and_format_chapter_title


# ---------------------------------------------------------------------------
# 1. Source Language Detection
# ---------------------------------------------------------------------------

def test_detect_source_language_korean():
    korean_sample = "인류를 다 죽일 뻔했던 미친 AI를 믿는 게 아니었다. “콜록, 콜록… 으에엑.”"
    assert detect_source_language(korean_sample) == "Korean"


def test_detect_source_language_chinese():
    chinese_sample = "不知何时，我已经习惯了破解别人的安保系统。负责护卫我的那位雇佣兵姐姐"
    assert detect_source_language(chinese_sample) == "Chinese"


def test_detect_source_language_japanese():
    japanese_sample = "俺の冒険がここから始まるんだと、強く信じていた。だけど現実は厳しかった。"
    assert detect_source_language(japanese_sample) == "Japanese"


def test_detect_source_language_empty_fallback():
    assert detect_source_language("") == "Chinese"
    assert detect_source_language(None) == "Chinese"


# ---------------------------------------------------------------------------
# 2. Core Translation Guidelines Adaptation
# ---------------------------------------------------------------------------

def test_korean_guidelines_direct_and_anti_double_translate():
    guidelines = build_core_translation_guidelines(lang_name="Indonesian", genre="system", source_lang="Korean")

    # Anti double-translate directives
    assert "Korean web novels" in guidelines
    assert "No Korean Hangul characters allowed" in guidelines
    assert "translate directly from Korean to Indonesian" in guidelines
    assert "Never introduce Chinese characters, Hanzi, or Pinyin" in guidelines

    # Korean-specific honorifics & conventions
    assert "형/Hyung" in guidelines or "오빠/Oppa" in guidelines
    assert "zero anaphora" in guidelines
    assert "헌터 = Hunter" in guidelines


def test_chinese_guidelines_backward_compatible():
    guidelines = build_core_translation_guidelines(lang_name="English", genre="cultivation", source_lang="Chinese")

    assert "Chinese web novels" in guidelines
    assert "No Chinese characters or pinyin allowed" in guidelines
    assert "Senior Brother" in guidelines


# ---------------------------------------------------------------------------
# 3. Title Translation Prompts
# ---------------------------------------------------------------------------

def test_korean_title_translation_prompt():
    prompt = build_title_translation_prompt(target_lang="Indonesian", source_lang="Korean")
    assert "from Korean into Indonesian" in prompt
    assert "ABSOLUTELY NO KOREAN HANGUL CHARACTERS ARE ALLOWED" in prompt


def test_chinese_title_translation_prompt_preserved():
    prompt = build_title_translation_prompt(target_lang="English", source_lang="Chinese")
    assert "from Chinese into English" in prompt
    assert "ABSOLUTELY NO CHINESE CHARACTERS OR PINYIN ARE ALLOWED" in prompt


# ---------------------------------------------------------------------------
# 4. Korean Chapter Title Cleaning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw_title,order_num,expected_name", [
    ("제1화 프롤로그", 1, "01. 프롤로그"),
    ("제 15 화 각성의 순간", 15, "15. 각성의 순간"),
    ("25화 던전 탐색", 25, "25. 던전 탐색"),
    ("EP.3 끝나지 않은 싸움", 3, "03. 끝나지 않은 싸움"),
    ("Episode 7 그림자 군주", 7, "07. 그림자 군주"),
])
def test_clean_and_format_korean_chapter_title(raw_title, order_num, expected_name):
    result = clean_and_format_chapter_title(raw_title, order_num=order_num, total_chapters=50)
    assert result == expected_name


# ---------------------------------------------------------------------------
# 5. Korean Glossary Extraction & Evidence Rules
# ---------------------------------------------------------------------------

def test_korean_glossary_extraction_prompt():
    prompt = build_glossary_extraction_prompt(target_lang="Indonesian", source_lang="Korean")
    assert "from the provided Korean text" in prompt
    assert "NEVER output notes or descriptions in Korean" in prompt
    assert "explicit 그/그녀 pronouns" in prompt
    assert "성진우 → Sung Jin-woo" in prompt
    assert "차해인 → Cha Hae-in" in prompt


# ---------------------------------------------------------------------------
# 6. Glossary Locking for Raw Korean Terms
# ---------------------------------------------------------------------------

class MockEntry:
    def __init__(self, original_term, translated_term, notes=""):
        self.original_term = original_term
        self.translated_term = translated_term
        self.notes = notes


def test_glossary_locking_replaces_raw_korean_terms():
    entries = [
        MockEntry(original_term="성진우", translated_term="Sung Jin-woo"),
        MockEntry(original_term="차해인", translated_term="Cha Hae-in"),
    ]
    rules = build_glossary_lock_rules(entries)
    text = "Keesokan harinya 성진우 bertemu dengan 차해인 di depan gerbang."
    locked = apply_glossary_lock(text, rules)

    assert "Sung Jin-woo" in locked
    assert "Cha Hae-in" in locked
    assert "성진우" not in locked
    assert "차해인" not in locked


# ---------------------------------------------------------------------------
# 7. ContextEngine Dynamic Detection Integration
# ---------------------------------------------------------------------------

def test_context_engine_build_prompt_adapts_to_korean_text():
    db = MagicMock()
    mock_gs = MagicMock()
    mock_gs.global_context = ""
    mock_gs.max_context_terms = 50
    db.execute.return_value.scalar_one_or_none.return_value = mock_gs
    db.execute.return_value.scalars.return_value.all.return_value = []

    korean_chapter = "인류를 다 죽일 뻔했던 미친 AI를 믿는 게 아니었다. 성진우는 결심했다."
    prompt = ContextEngine.build_translation_prompt(
        db=db,
        thread_id=1,
        target_lang="Indonesian",
        original_text=korean_chapter,
    )

    assert "Korean web novels" in prompt
    assert "translate directly from Korean to Indonesian" in prompt
