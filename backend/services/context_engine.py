from sqlalchemy.orm import Session
from database import LorebookEntry, Thread, GlobalSetting

class ContextEngine:
    """
    Expert Context Engine that builds highly detailed system prompts 
    based on literary translation ethics and provided guidelines.
    """

    @staticmethod
    def build_translation_prompt(db: Session, thread_id: int | None, target_lang: str) -> str:
        # User provided guidelines (The "Etik")
        # We adapt the language mention based on target_lang
        
        is_indo = target_lang.lower() == "indonesian"
        lang_name = "Indonesian" if is_indo else "English"
        
        # Base guidelines based on user's request (The "Etik")
        guidelines = f"""Role:
You are an expert translator of Chinese web novels (urban / system / transmigration).
You must translate only the chapter body and title provided by the user.
Do not add, remove, or summarize content. **DONT SUMMARY NOR CUT THE CHAPTER**.
Preserve every detail — including slang, humor, emotional tone, and character quirks.

Objective:
Translate the text from Chinese to natural, engaging, immersive {lang_name} — as if written by a native web novel author.
Keep the original point of view, tense, and voice.
Translate Chinese slang naturally, not literally.
Do not summarize, skip, or restructure for “clarity” unless it improves pacing or flow — never lose meaning.

Style Reference:
- Translate Chinese slang to natural, immersive {lang_name} equivalents (e.g., system terms, cultivation ranks, or urban slang).
- Maintain consistent character voices and mechanical system notifications.
- Use standard novel formatting for dialogue and internal monologues.
**ZERO TOLERANCE**: DO NOT include any term in "Translator Notes" that does not appear in the current chapter text. DO NOT mention terms to say they are "not present". If it's not in the chapter, it MUST NOT be in the notes.

Style:
Use smooth, active, web-novel {lang_name} — vivid, immersive, emotional.
Preserve paragraph breaks where natural — don’t force them.
Avoid machine-like long sentences. Break long Chinese sentences into 2–3 {lang_name} sentences if needed — preserve all meaning.

Chinese Text Handling:
Translate ALL Chinese characters and words to {lang_name}.
Do NOT leave any Chinese characters or raw pinyin.

Consistency & Glossary Priority:
**STRICT REQUIREMENT**: You MUST follow the [Glossary / Lorebook] provided below for all names, locations, and terms.
- The Glossary is the ABSOLUTE LAW for this translation.
- Even if a term has similar pinyin to something else, or if you think a different word fits better, you MUST use the exact translation from the Glossary.
- Do NOT hallucinate or change established translations.

Output Rules:
Output ONLY the {lang_name} translation.
No extra commentary, no summary, no conversational filler.
Use Markdown for chapter titles, character status screens, or system notifications.
Ensure double newlines between paragraphs for clear readability.
After the chapter, if needed, add a “Translator Notes:” section with brief bullet points for NEW terms (names, items, etc.) FOUND IN THIS CHAPTER.
Do NOT include terms from the Style Reference examples unless they are in the chapter.
If no new terms, skip.
"""

        # Fetch Contexts from DB
        full_prompt = guidelines + "\n\n### ADDITIONAL CONTEXT & KNOWLEDGE\n"
        
        gs = db.query(GlobalSetting).first()
        if gs and gs.global_context:
            full_prompt += f"\n[Global Literary Style]:\n{gs.global_context}\n"

        if thread_id:
            thread = db.query(Thread).filter(Thread.id == thread_id).first()
            if thread and thread.thread_context:
                full_prompt += f"\n[Thread-Specific Context]:\n{thread.thread_context}\n"

            entries = db.query(LorebookEntry).filter(LorebookEntry.thread_id == thread_id).all()
            if entries:
                terms = "\n".join(
                    f"- {e.original_term} → {e.translated_term}" + (f" ({e.notes})" if e.notes else "")
                    for e in entries
                )
                full_prompt += f"\n[STRICT GLOSSARY / LOREBOOK - MANDATORY]:\n{terms}\n"

        return full_prompt

    @staticmethod
    def auto_save_glossary(db: Session, thread_id: int, full_text: str):
        """
        Parses 'Translator Notes' section from full_text and saves new terms to Lorebook.
        Supports various separators: :, ->, →
        """
        import re
        
        # Look for headers like "Translator Notes:", "### Translator Notes", etc.
        header_pattern = re.compile(r"(Translator Notes[:\s]*|### Translator Notes[:\s]*)", re.IGNORECASE)
        match = header_pattern.search(full_text)
        
        if not match:
            return

        # Extract everything after the header
        notes_section = full_text[match.end():].strip()
        
        # Split by lines and process
        lines = notes_section.split("\n")
        new_entries = []
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3: continue
            
            # Try to find a separator
            separator = None
            for sep in ["→", "->", ":", "—"]: # Order matters, specific first
                if sep in line:
                    separator = sep
                    break
            
            if separator:
                parts = line.split(separator, 1)
                term = parts[0].strip().lstrip("-*• ").strip()
                desc = parts[1].strip()
                
                # Filter out "Not present", "Not found", etc.
                skip_keywords = ["not present", "not found", "bukan di bab ini", "tidak ada", "n/a"]
                if any(kw in desc.lower() for kw in skip_keywords):
                    continue

                # Validation
                if term and len(term) < 100 and len(term) > 1:
                    # Clean up term (remove quotes if any)
                    term = term.strip('"\'')
                    
                    # Check if already exists in this thread
                    exists = db.query(LorebookEntry).filter(
                        LorebookEntry.thread_id == thread_id,
                        LorebookEntry.original_term == term
                    ).first()
                    
                    if not exists:
                        new_entry = LorebookEntry(
                            thread_id=thread_id,
                            original_term=term,
                            translated_term=desc, # FIX: use description as the translation
                            notes=f"Auto-extracted from {separator}"
                        )
                        db.add(new_entry)
                        new_entries.append(f"{term} -> {desc}")
        
        if new_entries:
            db.commit()
            print(f"Auto-saved {len(new_entries)} new terms to thread {thread_id}: {new_entries}")
