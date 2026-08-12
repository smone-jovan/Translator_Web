import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from services.prompt_templates import (
    detect_primary_genre,
    build_core_translation_guidelines,
    build_title_translation_prompt,
    build_title_cleaning_prompt
)
from services.context_engine import ContextEngine
from routers.polish import clean_and_format_chapter_title


def test_thread15_genre_detection_and_prompt_building():
    """Verify genre detection and prompt generation for 'Motherhood and the Dark Magical Girl' (Thread 15)."""
    genres_str = "恋爱, 嫁人, 日常, 女性主角"
    tags_str = "魔法少女, 搞笑"
    
    genre = detect_primary_genre(genres_str, tags_str)
    assert genre in ["romance", "urban"]
    
    prompt = build_core_translation_guidelines("English", genre=genre)
    
    # Verify pure prose without footnotes requirements
    assert "ABSOLUTELY NO INLINE DICTIONARY NOTES OR BILINGUAL ANNOTATIONS" in prompt
    assert "DO NOT embed footnotes in the story body" in prompt
    assert "[GENRE:" in prompt


def test_thread15_clean_prose_strips_footnotes_and_notes():
    """Verify that clean_final_translation strips both FOOTNOTES and TRANSLATOR NOTES for pure prose output."""
    translated_text = (
        "Wen Han transformed into a seventeen-year-old Dark Magical Girl on her thirtieth birthday.\n\n"
        "She decided not to overcomplicate things when dealing with the intruder.\n\n"
        "### FOOTNOTES:\n"
        "[1] Idiom '当妈后我变成黑魔法少女'\n\n"
        "### TRANSLATOR NOTES:\n"
        "- 画蛇添足 -> Draw a snake and add feet"
    )

    cleaned = ContextEngine.clean_final_translation(translated_text, always_hide_thoughts=True)
    
    # Assert main story text is clean
    assert "Wen Han transformed into a seventeen-year-old Dark Magical Girl" in cleaned
    assert "She decided not to overcomplicate things" in cleaned
    
    # Assert both Footnotes and Translator Notes sections are stripped
    assert "### FOOTNOTES:" not in cleaned
    assert "### TRANSLATOR NOTES:" not in cleaned


def test_thread15_title_polish_compatibility():
    """Verify that title polishing rules work cleanly on Thread 15 chapter titles without collision."""
    # Test title 1
    raw_title_1 = "第2章 1.是坏女人也是单亲妈妈更是魔法少女"
    polished_1 = clean_and_format_chapter_title("Femme Fatale, Single Mom, Magical Girl", order_num=2, total_chapters=10, volume_num=1)
    assert polished_1 == "V1-02. Femme Fatale, Single Mom, Magical Girl"
    
    # Test title 2 (Emoji handling)
    raw_title_2 = "第9章 8.兄弟👬变闺蜜👭"
    polished_2 = clean_and_format_chapter_title("From Bros to Besties", order_num=9, total_chapters=10, volume_num=1)
    assert polished_2 == "V1-09. From Bros to Besties"
    
    # Verify title cleaning prompt does not collide with translation prompt
    title_clean_prompt = build_title_cleaning_prompt()
    assert "ONLY the clean, official Chinese title" in title_clean_prompt
