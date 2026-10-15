import pytest
from services.fidelity_checker import (
    count_untranslated_script_chars,
    verify_translation_fidelity,
    is_truncated_mid_sentence,
)

def test_verify_fidelity_normal_length():
    """Test that a translation of normal length is not flagged as suspicious."""
    # 5 paragraphs translated to 5 paragraphs
    original = "Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4.\n\nPara 5."
    translated = "Paragraf 1.\n\nParagraf 2.\n\nParagraf 3.\n\nParagraf 4.\n\nParagraf 5."
    
    result = verify_translation_fidelity(original, translated, chapter_id=1)
    
    assert result["is_suspicious"] is False
    assert result["original_paragraphs"] == 5
    assert result["translated_paragraphs"] == 5
    assert result["paragraph_ratio"] == 1.0
    assert result["is_truncated"] is False

def test_verify_fidelity_suspicious_drop():
    """Test that a severely truncated translation (< 0.3 ratio) is flagged."""
    # 10 paragraphs translated to only 2 (LLM skipped content)
    original = "\n\n".join([f"Paragraph {i} content text with sufficient length." for i in range(10)])
    translated = "\n\n".join([f"Paragraf {i} content text with sufficient length." for i in range(2)])
    
    result = verify_translation_fidelity(original, translated, chapter_id=2)
    
    assert result["is_suspicious"] is True
    assert result["paragraph_ratio"] == 0.2  # 2 / 10
    assert any("Paragraph count dropped significantly" in w for w in result["warnings"])

def test_verify_fidelity_suspicious_hallucination():
    """Test that a severely elongated translation (> 2.5 ratio) is flagged."""
    # 2 paragraphs translated to 10 (LLM hallucinated loop)
    original = "Short paragraph 1.\n\nVery short paragraph 2."
    translated = "\n\n".join([f"Paragraf {i} content text." for i in range(10)])
    
    result = verify_translation_fidelity(original, translated, chapter_id=3)
    
    assert result["is_suspicious"] is True
    assert result["paragraph_ratio"] == 5.0  # 10 / 2
    assert any("Paragraph count inflated" in w for w in result["warnings"])

def test_verify_fidelity_ignores_image_markers():
    """Test that image placeholder markers do not artificially inflate paragraph count."""
    original = "Text 1.\n\n![Image](url)\n\nText 2."
    translated = "Teks 1.\n\n❖IMAGE_0❖\n\nTeks 2."
    
    result = verify_translation_fidelity(original, translated, chapter_id=4)
    assert result["is_suspicious"] is False
    assert result["translated_paragraphs"] == 3

def test_valid_novel_endings_no_false_positive():
    """Test that valid web novel punctuation (quotes, brackets, emojis, semicolons, end tags, cliffhangers) are not flagged as truncated."""
    assert is_truncated_mid_sentence("Kalimat selesai dengan petik tunggal '") is False
    assert is_truncated_mid_sentence("Kalimat selesai dengan petik ganda \"") is False
    assert is_truncated_mid_sentence("Notifikasi sistem selesai [Status Level Up: Max]") is False
    assert is_truncated_mid_sentence("Suasana hati bergembira sekali♥") is False
    assert is_truncated_mid_sentence("Dialog dengan kurung Jepang 「Terima kasih」") is False
    assert is_truncated_mid_sentence("Kalimat penutup berurutan;") is False
    assert is_truncated_mid_sentence("Format penekanan dialog *'Pasti tidak akan kalah.'*") is False
    assert is_truncated_mid_sentence("**Bab Selesai.**") is False
    # Chapter-ending markers
    assert is_truncated_mid_sentence("- The End") is False
    assert is_truncated_mid_sentence("It was Celine Alice.\n\n- The End") is False
    assert is_truncated_mid_sentence("[To be continued]") is False
    assert is_truncated_mid_sentence("第164章 完") is False
    # Original matching cliffhanger endings
    assert is_truncated_mid_sentence("My mother", original_text="我的母亲——") is False
    assert is_truncated_mid_sentence("Taking the first step toward the judgment of the Beldia family", original_text="向着审判贝尔迪亚家族的第一步——") is False


def test_real_truncations_detected():
    """Test that genuine mid-sentence cutoffs are properly flagged."""
    assert is_truncated_mid_sentence("Tiba-tiba dia berkata bahwa") is True
    assert is_truncated_mid_sentence("With aggressive momentum,") is True
    assert is_truncated_mid_sentence("Listening to explanations couldn't") is True
    assert is_truncated_mid_sentence("Dissolving instantly, it transformed into a") is True
    assert is_truncated_mid_sentence("") is True


def test_verify_fidelity_paragraph_consolidation_not_suspicious():
    """Test that micro-line web novel text consolidated into prose with healthy char length is not flagged as suspicious."""
    # 30 short lines (avg ~15 chars each = 450 chars)
    original = "\n\n".join([f"短行内容测试第 {i} 句。" for i in range(30)])
    # 5 standard English prose paragraphs (avg ~150 chars each = 750 chars, char_ratio = 1.66x)
    translated = "\n\n".join([
        f"This is a properly consolidated narrative paragraph number {i} grouping multiple short source sentences together with complete phrasing and proper punctuation."
        for i in range(5)
    ])

    result = verify_translation_fidelity(original, translated, chapter_id=99)
    assert result["paragraph_ratio"] < 0.3  # 5 / 30 = 0.17
    assert result["char_ratio"] >= 1.0
    assert result["is_truncated"] is False
    assert result["is_suspicious"] is False
    assert any("Paragraph count consolidated" in w for w in result["warnings"])


def test_count_untranslated_script_chars():
    """Ensure raw CJK, Hangul, and Kana characters are counted while excluding image alt text and allowed kaomoji."""
    text_with_cjk = "Lin En menatap ke langit: 这是什么？ (Ini apa?)"
    # 这是什么？ has 4 Hanzi
    assert count_untranslated_script_chars(text_with_cjk) == 4

    # Kaomoji characters like 囧, 凸, ㅠㅠ should be ignored
    kaomoji_text = "Dia tersenyum kecut 囧 dan menangis ㅠㅠ sambil tertawa ㅋㅋ."
    assert count_untranslated_script_chars(kaomoji_text) == 0

    # Markdown image alt text with Chinese characters should be excluded
    img_text = "Paragraf pembuka.\n\n![插图](https://example.com/img.jpg)\n\nParagraf penutup."
    assert count_untranslated_script_chars(img_text) == 0


def test_verify_fidelity_script_leakage():
    """Test that leaked source script in translation is flagged as suspicious."""
    cjk_orig = "\n\n".join([f"第{i}段：林恩看着眼前的古老神殿，心中涌起一股难以言喻的敬畏之情。" for i in range(10)])
    leaked_trans = "\n\n".join([
        "Paragraf 1: Lin En menatap kuil kuno di hadapannya dengan rasa kagum.",
        "Paragraf 2: 第2段：林恩看着眼前的古老神殿，心中涌起一股难以言喻的敬畏之情。",
        "Paragraf 3: Dia melangkah masuk ke dalam aula utama.",
    ])

    result = verify_translation_fidelity(cjk_orig, leaked_trans, chapter_id=10)
    assert result["is_suspicious"] is True
    assert result["untranslated_script_chars"] >= 15
    assert any("Untranslated source script detected" in w for w in result["warnings"])


def test_verify_fidelity_cjk_summarization_drop():
    """Test that severe paragraph drop on CJK source with low char_ratio is flagged as AI summarization."""
    # orig_chars >= 600, char_ratio < 0.70 (and >= 0.30), para_ratio < 0.65
    cjk_orig = "\n\n".join([f"第{i}段：这是关于修仙界林恩历经千辛万苦突破元婴期的详细战斗经过与心理描写。" for i in range(25)])
    summary_trans = "\n\n".join([
        "Lin En berhasil menembus tahap Nascent Soul setelah melalui pertarungan sengit yang menguras seluruh tenaga dan staminanya melawan musuh bebuyutannya di puncak gunung es kuno.",
        "Setelah mencapai terobosan ini, aura spiritual di sekeliling tubuhnya berfluktuasi dengan sangat dahsyat, menandai babak baru dalam perjalanan kultivasi panjang yang penuh dengan marabahaya dan rintangan.",
    ])

    result = verify_translation_fidelity(cjk_orig, summary_trans, chapter_id=20)
    assert result["is_suspicious"] is True
    assert 0.30 <= result["char_ratio"] < 0.70
    assert result["paragraph_ratio"] < 0.65
    assert any("AI summarization or skipped paragraphs" in w for w in result["warnings"])


def test_verify_fidelity_hallucination_loop_and_meta_leakage():
    """Test detection of repetition loops and AI sentinel/preamble leakage."""
    cjk_orig = "这是一段正常的玄幻修仙测试文本，用来作为对照测试源文。\n\n主角继续前行。"
    loop_trans = "Dia menatap langit. " + "menatap langit malam " * 10 + "lalu terdiam."
    res_loop = verify_translation_fidelity(cjk_orig, loop_trans, chapter_id=30)
    assert res_loop["is_suspicious"] is True
    assert res_loop["has_hallucination_loop"] is True
    assert any("Hallucination repetition loop detected" in w for w in res_loop["warnings"])

    meta_trans = "Berikut adalah terjemahan teks:\n\nLin En melangkah maju ke depan aula utama."
    res_meta = verify_translation_fidelity(cjk_orig, meta_trans, chapter_id=31)
    assert res_meta["is_suspicious"] is True
    assert any("AI meta-commentary or truncation sentinel leaked" in w for w in res_meta["warnings"])


