import pytest
from services.fidelity_checker import verify_translation_fidelity, is_truncated_mid_sentence

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
    """Test that valid web novel punctuation (quotes, brackets, emojis, semicolons) are not flagged as truncated."""
    assert is_truncated_mid_sentence("Kalimat selesai dengan petik tunggal '") is False
    assert is_truncated_mid_sentence("Kalimat selesai dengan petik ganda \"") is False
    assert is_truncated_mid_sentence("Notifikasi sistem selesai [Status Level Up: Max]") is False
    assert is_truncated_mid_sentence("Suasana hati bergembira sekali♥") is False
    assert is_truncated_mid_sentence("Dialog dengan kurung Jepang 「Terima kasih」") is False
    assert is_truncated_mid_sentence("Kalimat penutup berurutan;") is False
    assert is_truncated_mid_sentence("Format penekanan dialog *'Pasti tidak akan kalah.'*") is False
    assert is_truncated_mid_sentence("**Bab Selesai.**") is False

def test_real_truncations_detected():
    """Test that genuine mid-sentence cutoffs are properly flagged."""
    assert is_truncated_mid_sentence("Tiba-tiba dia berkata bahwa") is True
    assert is_truncated_mid_sentence("With aggressive momentum,") is True
    assert is_truncated_mid_sentence("Listening to explanations couldn't") is True
    assert is_truncated_mid_sentence("Dissolving instantly, it transformed into a") is True
    assert is_truncated_mid_sentence("") is True
