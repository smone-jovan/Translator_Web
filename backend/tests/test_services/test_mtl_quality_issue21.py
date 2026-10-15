from unittest.mock import AsyncMock, patch
import pytest

from services.hallucination_detector import HallucinationDetector
from services.fidelity_checker import verify_translation_fidelity
from services.glossary_lock import build_glossary_lock_rules, apply_glossary_lock
from services.prompt_templates import (
    build_core_translation_guidelines,
    build_title_translation_prompt,
    build_glossary_extraction_prompt,
)
from services.context_engine import ContextEngine
from services.ai.gemini import GeminiAdapter
from services.ai.base import TRUNCATED_MARKER


@pytest.mark.asyncio
async def test_gemini_truncation_preserves_partial_text():
    """
    When Gemini hits finish_reason == 'length', chat_completion must return the partial text
    and stream_chat must yield the partial text BEFORE yielding TRUNCATED_MARKER.
    """
    adapter = GeminiAdapter(api_key="test-key", model="gemini-2.5-flash")
    partial_story = "Bagian pertama bab yang sangat panjang dan terpotong di tengah kalimat karena batas token"
    with patch.object(adapter, "_try_chat_completion", new_callable=AsyncMock) as mock_try:
        mock_try.return_value = (partial_story, "length", {"usage": {}})
        res_chat = await adapter.chat_completion([{"role": "user", "content": "Translate"}])
        assert res_chat == partial_story

        chunks = [c async for c in adapter.stream_chat([{"role": "user", "content": "Translate"}])]
        assert chunks == [partial_story, TRUNCATED_MARKER]


def test_hallucination_detector_multiword_phrase_loops():
    """
    HallucinationDetector must detect and collapse multi-word N-gram phrase repetition loops.
    """
    loop_text = (
        "Dia menggenggam pedangnya erat-erat.\n\n"
        "Dia menatap langit malam, dia menatap langit malam, dia menatap langit malam, "
        "dia menatap langit malam, dia menatap langit malam.\n\n"
        "Lalu ia melangkah maju."
    )
    phrase_matches = HallucinationDetector.detect_repeated_phrases(loop_text, threshold=4)
    assert len(phrase_matches) >= 1
    assert "dia menatap langit malam" in phrase_matches[0].token.lower()

    cleaned_loop = HallucinationDetector.strip_repetitive_character_loops(loop_text)
    assert cleaned_loop.lower().count("dia menatap langit malam") == 1
    assert "Lalu ia melangkah maju." in cleaned_loop


def test_fidelity_checker_script_leakage_and_kaomoji_safety():
    """
    verify_translation_fidelity must flag raw CJK/Hangul/Kana script leakage
    while ignoring visual kaomoji (囧, 凸, ㅠㅠ) and markdown image alt-text 插图.
    """
    cjk_orig = "\n\n".join([f"第{i}段：林恩看着眼前的古老神殿，心中涌起一股难以言喻的敬畏之情。" for i in range(10)])
    leaked_trans = "\n\n".join([
        "Paragraf 1: Lin En menatap kuil kuno di hadapannya dengan rasa kagum.",
        "Paragraf 2: 第2段：林恩看着眼前的古老神殿，心中涌起一股难以言喻的敬畏之情。",
        "Paragraf 3: Dia melangkah masuk ke dalam aula utama.",
    ])
    fid_leak = verify_translation_fidelity(cjk_orig, leaked_trans, chapter_id=10)
    assert fid_leak["is_suspicious"] is True
    assert fid_leak["untranslated_script_chars"] >= 15
    assert any("Untranslated source script detected" in w for w in fid_leak["warnings"])

    clean_with_kaomoji_and_img = (
        "Paragraf 1: Lin En tersenyum kecut 囧 saat melihat ekspresi mereka (⊙_⊙).\n\n"
        "![插图](https://example.com/img.jpg)\n\n"
        + "\n\n".join([f"Paragraf {i}: Mereka melanjutkan perjalanan melewati lembah berkabut dengan hati-hati." for i in range(2, 11)])
    )
    fid_clean = verify_translation_fidelity(cjk_orig, clean_with_kaomoji_and_img, chapter_id=11)
    assert fid_clean["untranslated_script_chars"] == 0
    assert fid_clean["is_suspicious"] is False


def test_glossary_lock_protects_urls_and_locks_indonesian_clitics():
    """
    apply_glossary_lock must never corrupt Markdown image URLs or HTML tags,
    and must lock names with attached Indonesian clitics (-nya, -mu, -ku).
    """
    class DummyEntry:
        def __init__(self, orig, trans, notes=None):
            self.original_term = orig
            self.translated_term = trans
            self.notes = notes

    rules = build_glossary_lock_rules([
        DummyEntry("罗毅 (Luo Yi / Luoyi)", "Rahmat"),
        DummyEntry("插图", "Ilustrasi"),
    ])
    md_with_img_and_clitic = (
        "Pedang milik Luoyinya berkilau tajam saat Luo Yi-nya menebas musuh.\n\n"
        "![插图](https://example.com/插图/Luoyi.png)\n\n"
        '<img src="https://cdn.example.com/Luoyi_action.jpg" alt="Luoyi" />'
    )
    locked = apply_glossary_lock(md_with_img_and_clitic, rules)
    assert "Pedang milik Rahmatnya berkilau tajam saat Rahmat-nya menebas musuh." in locked
    assert "https://example.com/插图/Luoyi.png" in locked
    assert 'src="https://cdn.example.com/Luoyi_action.jpg"' in locked


def test_clean_final_translation_strips_ai_wrappers_and_inline_bilingual_notes():
    """
    ContextEngine.clean_final_translation must strip AI conversational preambles/postambles
    and inline bilingual dictionary notes while preserving kaomoji and translated reaction tags.
    """
    raw = (
        "Berikut adalah terjemahan bahasa Indonesia untuk bab ini:\n\n"
        "Song Shuhang (宋书航) menatap Sekte Awan Biru (Pinyin: Qing Yun Zong) dengan tatapan serius (keringat dingin) (⊙_⊙).\n"
        "Dia mengayunkan pedangnya [TL Note: Pedang warisan leluhur] dengan cepat.\n\n"
        "--- End of Translation ---"
    )
    cleaned = ContextEngine.strip_inline_bilingual_notes(ContextEngine.strip_ai_conversational_wrappers(raw))
    assert "Berikut adalah terjemahan" not in cleaned
    assert "(宋书航)" not in cleaned
    assert "(Pinyin: Qing Yun Zong)" not in cleaned
    assert "[TL Note:" not in cleaned
    assert "End of Translation" not in cleaned
    assert "(keringat dingin)" in cleaned
    assert "(⊙_⊙)" in cleaned


def test_prompt_templates_indonesian_honorifics_and_japanese_source_support():
    """
    build_core_translation_guidelines must use target language honorifics for Indonesian
    and support Japanese source texts across core, title, and glossary prompts.
    """
    indo_chinese_prompt = build_core_translation_guidelines("Indonesian", genre="cultivation", source_lang="Chinese")
    assert "into Indonesian" in indo_chinese_prompt
    assert "Kakak Senior" in indo_chinese_prompt
    assert "Tetua" in indo_chinese_prompt
    assert "Translate Chinese honorifics to English" not in indo_chinese_prompt

    en_chinese_prompt = build_core_translation_guidelines("English", genre="cultivation", source_lang="Chinese")
    assert "Senior Brother" in en_chinese_prompt

    jp_prompt = build_core_translation_guidelines("Indonesian", genre="default", source_lang="Japanese")
    assert "Japanese web novels" in jp_prompt
    assert "No Japanese Hiragana, Katakana, or Kanji" in jp_prompt
    assert "-senpai" in jp_prompt

    jp_title_prompt = build_title_translation_prompt("Indonesian", source_lang="Japanese")
    assert "from Japanese into Indonesian" in jp_title_prompt
    assert "NO JAPANESE KANA OR KANJI" in jp_title_prompt

    jp_glossary_prompt = build_glossary_extraction_prompt("Indonesian", source_lang="Japanese")
    assert "from the provided Japanese text" in jp_glossary_prompt
