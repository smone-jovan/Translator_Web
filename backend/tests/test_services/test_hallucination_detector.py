import pytest
from services.hallucination_detector import HallucinationDetector
from services.context_engine import ContextEngine


class TestHallucinationDetector:
    """Comprehensive test suite for HallucinationDetector and word-soup stripping."""

    def test_detect_repeated_words_basic(self):
        text = "The villain shouted " + "die " * 15 + "as he attacked."
        matches = HallucinationDetector.detect_repeated_words(text, threshold=10)
        assert len(matches) == 1
        assert matches[0].token.lower() == "die"
        assert matches[0].count == 15

    def test_detect_repeated_words_none_when_normal(self):
        text = "Senior Sister walked across the courtyard and greeted her junior disciple."
        matches = HallucinationDetector.detect_repeated_words(text, threshold=10)
        assert len(matches) == 0

    def test_strip_word_soup_hallucinations_dictionary_dump(self):
        """Test stripping dictionary dumps with 20+ space-separated words with no punctuation."""
        text = (
            "Chapter 6: Training the Dog (Part II)\n\n"
            "\"Senior Sister...\" My voice trembled, and tears finally spilled over. \"Don't do this... Please...\"\n\n"
            "society civilization history era period age decade century millennium year month day hour minute second "
            "tick tock clock watch timer stopwatch chronometer calendar date timestamp label tag keyword search query "
            "filter sort order rank score point mark symbol icon image picture photo video audio sound noise music rhythm\n\n"
            "Liu Ruyue ignored my pleas. She tugged on the chain with a light force that carried an undeniable command.\n\n"
            "unbone unmuscle untendon unligament unnerve unblood unvein unartery unheart unlung unliver unkidney "
            "unspleen unstomach unintestine unconcolon unrectum unanus unmouth unnose uneareye unhand unfoot unarm unleg"
        )
        cleaned = HallucinationDetector.strip_word_soup_hallucinations(text)
        
        # Word soup paragraphs should be gone
        assert "society civilization" not in cleaned
        assert "unbone unmuscle" not in cleaned
        
        # Legitimate story text must be completely preserved
        assert "Chapter 6: Training the Dog (Part II)" in cleaned
        assert "\"Senior Sister...\"" in cleaned
        assert "Liu Ruyue ignored my pleas" in cleaned

    def test_strip_word_soup_mid_paragraph_truncation(self):
        """Test that word soup starting mid-paragraph truncates only the soup, preserving the prefix."""
        text = (
            "The ancient master nodded gently and opened the sacred gate for the disciples. "
            "gear unshaft unaxle unwheel unirim untire unrubber unplastic unmetal unwood unstone unpaper "
            "uncloth unfabric unsilk uncotton unwool unlinen unleather unfur unhair uninskin"
        )
        cleaned = HallucinationDetector.strip_word_soup_hallucinations(text)
        assert "The ancient master nodded gently and opened the sacred gate for the disciples." in cleaned
        assert "unaxle unwheel" not in cleaned

    def test_strip_word_soup_preserves_legitimate_prose_and_dialogue(self):
        """Ensure normal dialogue, lists with commas, and long sentences are NEVER stripped."""
        legitimate_prose = (
            "Chapter 10: The Grand Assembly\n\n"
            "\"Listen carefully,\" Elder Zhang proclaimed. \"The Azure Cloud Sect requires courage, discipline, "
            "respect, diligence, and unwavering loyalty from every prospective disciple.\"\n\n"
            "Over five hundred young cultivators stood under the scorching midday sun. Some held wooden swords, "
            "others carried jade talismans, and a few wore ornate silk robes bearing family crests from the Capital."
        )
        cleaned = HallucinationDetector.strip_word_soup_hallucinations(legitimate_prose)
        assert cleaned == legitimate_prose

    def test_clean_final_translation_integration_strips_word_soup(self):
        """Test that ContextEngine.clean_final_translation strips word soup and thinking tags."""
        raw_output = (
            "<think>\nTranslating erotic cultivation chapter.\n</think>\n\n"
            "She stepped into the cave dwelling.\n\n"
            "investigations analyses conclusions findings results outcomes effects impacts consequences "
            "implications meanings significances values worths prices costs benefits gains profits losses "
            "damages injuries harms destructions creations formations structures organizations\n\n"
            "### TRANSLATOR NOTES:\n"
            "- 洞府 → Cave Dwelling"
        )
        cleaned = ContextEngine.clean_final_translation(raw_output, always_hide_thoughts=True)
        
        assert "<think>" not in cleaned
        assert "TRANSLATOR NOTES" not in cleaned
        assert "investigations analyses" not in cleaned
        assert "She stepped into the cave dwelling." in cleaned
