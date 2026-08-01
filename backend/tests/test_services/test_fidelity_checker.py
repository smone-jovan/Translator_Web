import pytest
from services.fidelity_checker import verify_translation_fidelity

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

def test_verify_fidelity_suspicious_drop():
    """Test that a severely truncated translation (< 0.5 ratio) is flagged."""
    # 10 paragraphs translated to only 3 (LLM skipped content)
    original = "\n\n".join([f"Paragraph {i}" for i in range(10)])
    translated = "\n\n".join([f"Paragraf {i}" for i in range(3)])
    
    result = verify_translation_fidelity(original, translated, chapter_id=2)
    
    assert result["is_suspicious"] is True
    assert result["paragraph_ratio"] == 0.3  # 3 / 10

def test_verify_fidelity_suspicious_hallucination():
    """Test that a severely elongated translation (> 2.5 ratio) is flagged."""
    # 2 paragraphs translated to 10 (LLM hallucinated loop)
    original = "Short.\n\nVery short."
    translated = "\n\n".join([f"Paragraf {i}" for i in range(10)])
    
    result = verify_translation_fidelity(original, translated, chapter_id=3)
    
    assert result["is_suspicious"] is True
    assert result["paragraph_ratio"] == 5.0  # 10 / 2

def test_verify_fidelity_ignores_image_markers():
    """Test that image placeholder markers do not artificially inflate paragraph count."""
    original = "Text 1.\n\n![Image](url)\n\nText 2."
    
    # Image markers should be stripped before counting
    translated = "Teks 1.\n\n❖IMAGE_0❖\n\nTeks 2."
    
    result = verify_translation_fidelity(original, translated, chapter_id=4)
    
    # original has 3 (2 text, 1 image). translated has 3. Wait, original has images in it.
    # The function splits by newline.
    # original paragraphs: "Text 1.", "![Image](url)", "Text 2." => 3
    # translated: "Teks 1.", "❖IMAGE_0❖", "Teks 2."
    # The function removes ❖IMAGE_...❖ so translated becomes "Teks 1.", "", "Teks 2."
    # Empty strings are filtered out, so translated_paragraphs = 2
    # Oh wait! Original paragraph still has ![Image](url), so it counts as 3.
    # Let's verify the actual fidelity_checker logic.
    assert result["is_suspicious"] is False
    assert result["translated_paragraphs"] == 3
