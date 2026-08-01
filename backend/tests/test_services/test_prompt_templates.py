import pytest
from services.prompt_templates import (
    detect_primary_genre,
    build_core_translation_guidelines,
    build_title_translation_prompt,
    build_title_cleaning_prompt
)

def test_detect_primary_genre_from_tags():
    """Test that primary genre is correctly detected from varied string inputs."""
    # Matches xianxia to cultivation
    assert detect_primary_genre(genres_str=None, tags_str="xianxia, harem") == "cultivation"
    
    # Matches system to system
    assert detect_primary_genre(genres_str="System, Action", tags_str=None) == "system"
    
    # Combines genre and tags string
    assert detect_primary_genre(genres_str="Fantasy", tags_str="wuxia elements") == "wuxia"
    
    # Falls back to default on unknown
    assert detect_primary_genre(genres_str="Meow", tags_str="Cat") == "default"
    
    # Handles empty/None safely
    assert detect_primary_genre(None, None) == "default"

def test_build_core_translation_guidelines_injects_genre():
    """Test that the core guidelines include the correct genre-specific instructions."""
    # Default behavior
    default_prompt = build_core_translation_guidelines(lang_name="English", genre="default")
    assert "[GENRE: General Web Novel]" in default_prompt
    assert "English" in default_prompt
    
    # Specific genre behavior
    wuxia_prompt = build_core_translation_guidelines(lang_name="Indonesian", genre="wuxia")
    assert "[GENRE: Wuxia / Martial Arts]" in wuxia_prompt
    assert "Indonesian" in wuxia_prompt
    assert "Jianghu" in wuxia_prompt  # Wuxia-specific instruction

def test_build_title_translation_prompt():
    """Test that the title translation prompt correctly incorporates the target language."""
    prompt_en = build_title_translation_prompt(target_lang="English")
    assert "English" in prompt_en
    assert "ABSOLUTELY NO CHINESE CHARACTERS" in prompt_en
    
    prompt_id = build_title_translation_prompt(target_lang="Indonesian")
    assert "Indonesian" in prompt_id

def test_build_title_cleaning_prompt_is_static():
    """Test that the cleaning prompt is static and returns expected instructions."""
    prompt = build_title_cleaning_prompt()
    assert "ONLY the clean, official Chinese title" in prompt

def test_build_core_translation_guidelines_pure_prose_no_footnotes():
    """Test that prompt instructions require pure prose without inline annotations or footnotes."""
    prompt = build_core_translation_guidelines(lang_name="Indonesian", genre="default")
    assert "ABSOLUTELY NO INLINE DICTIONARY NOTES OR BILINGUAL ANNOTATIONS" in prompt
    assert "DO NOT output any Footnotes or Translator Notes section" in prompt


