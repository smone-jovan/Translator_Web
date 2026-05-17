import unittest
import sys
import os
import re

# Set UTF-8 encoding for Windows standard out to prevent CP1252 UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Set system path to load backend directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.context_engine import ContextEngine

class TestContextEngine(unittest.TestCase):
    def test_strip_translator_notes_normal(self):
        text = "This is a beautiful chapter text. Winnie walked into the forest."
        result = ContextEngine.strip_translator_notes(text)
        self.assertEqual(result, text)

    def test_strip_translator_notes_basic(self):
        text = (
            "Winnie sat under the tree.\n\n"
            "Translator Notes:\n"
            "Winnie -> 文尼: The main character\n"
            "Luna -> 露娜: Trusted companion"
        )
        result = ContextEngine.strip_translator_notes(text)
        self.assertEqual(result, "Winnie sat under the tree.")

    def test_strip_translator_notes_markdown_header(self):
        text = (
            "Amisha started cooking the stew.\n\n"
            "### Translator's Notes\n"
            "Stew -> 炖菜\n"
        )
        result = ContextEngine.strip_translator_notes(text)
        self.assertEqual(result, "Amisha started cooking the stew.")

    def test_strip_translator_notes_trailing_stars(self):
        text = (
            "Luna smiled reassuringly.**\n\n"
            "--- Translator Notes ---\n"
            "Luna: 露娜"
        )
        result = ContextEngine.strip_translator_notes(text)
        self.assertEqual(result, "Luna smiled reassuringly.")

    def test_strip_translator_notes_empty(self):
        self.assertEqual(ContextEngine.strip_translator_notes(""), "")
        self.assertEqual(ContextEngine.strip_translator_notes(None), "")

    def test_auto_save_glossary(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base, Thread, LorebookEntry

        engine = create_engine("sqlite:///:memory:")
        Session = sessionmaker(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = Session()

        # Seed thread
        thread = Thread(id=1, title="Test Thread")
        db.add(thread)
        db.commit()

        # Call auto_save_glossary with diverse notes section
        text = (
            "Winnie arrived at the Elven Forest.\n\n"
            "Translator Notes:\n"
            "文尼 -> Winnie\n"
            "米莲 -> Millian\n"
            "This is a sentence and should be skipped because it contains no Chinese characters\n"
            "Some garbage words like Final List should be skipped\n"
        )
        ContextEngine.auto_save_glossary(db, 1, text)

        # Query all lorebook entries
        entries = db.query(LorebookEntry).filter(LorebookEntry.thread_id == 1).all()
        
        # Verify only the Chinese terms with proper Hanzi were successfully saved
        terms = {e.original_term: e.translated_term for e in entries}
        self.assertEqual(len(terms), 2)
        self.assertIn("文尼", terms)
        self.assertIn("米莲", terms)
        self.assertEqual(terms["文尼"], "Winnie")
        self.assertEqual(terms["米莲"], "Millian")

        db.close()

if __name__ == '__main__':
    unittest.main()
