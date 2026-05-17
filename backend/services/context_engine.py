from sqlalchemy import select
from sqlalchemy.orm import Session
from database import LorebookEntry, Thread, GlobalSetting

class ContextEngine:
    """
    Urusan bikin prompt buat LLM biar translasinya gak ngaco dan konsisten sama istilah sebelumnya.
    """

    @staticmethod
    def build_translation_prompt(db: Session, thread_id: int | None, target_lang: str, original_text: str | None = None) -> str:
        # Atur bahasa target (Indo atau Inggris)
        is_indo = target_lang.lower() == "indonesian"
        lang_name = "Indonesian" if is_indo else "English"
        
        # Ini core instruksi buat AI-nya. Isinya aturan etika translasi yang diminta user.
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

[CORE ETHICS & RULES]:
1. Context over Dictionary: Always deduce the entity type and domain from the provided context (e.g., surrounding text, sibling terms in a cluster). Prioritize structural alignment with existing translations over generic dictionary lookups.
2. Translate vs Transliterate: Fully translate objects, artifacts, techniques, and fictional organizations into English. Keep character names and established real-world proper nouns romanized.
3. World-Building Context: Do not blindly map terms to real-world locations if the text is a fantasy or historical setting (e.g., translate 京都 as 'The Capital' or 'Imperial Capital' rather than 'Kyoto' unless the context explicitly refers to the real-world city).
4. Honorifics & Address: Follow source language norms. Translate Chinese honorifics to English (e.g., Senior Brother, Elder, Young Master). Retain common Japanese (e.g., -san, -senpai) and Korean (e.g., -ssi, sunbae) honorifics as romanized suffixes/words.

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
**FORMAT**: You MUST use this exact format: '- Original Chinese Term → Translated Term (Brief notes tentang istilah tersebut)'.
Do NOT include terms from the Style Reference examples unless they are in the chapter.
If no new terms, skip.
"""

        # Gabungkan semua context tambahan (Global & Thread-specific)
        full_prompt = guidelines + "\n\n### ADDITIONAL CONTEXT & KNOWLEDGE\n"
        
        gs_stmt = select(GlobalSetting)
        gs = db.execute(gs_stmt).scalar_one_or_none()
        if gs and gs.global_context:
            full_prompt += f"\n[Global Literary Style]:\n{gs.global_context}\n"

        if thread_id:
            thread_stmt = select(Thread).where(Thread.id == thread_id)
            thread = db.execute(thread_stmt).scalar_one_or_none()
            if thread and thread.thread_context:
                full_prompt += f"\n[Thread-Specific Context]:\n{thread.thread_context}\n"

            # Ambil 50 istilah yang paling sering dipakai atau yang terbaru biar AI gak overload
            from sqlalchemy import desc
            entries_stmt = (
                select(LorebookEntry)
                .where(LorebookEntry.thread_id == thread_id)
                .order_by(desc(LorebookEntry.usage_count), desc(LorebookEntry.last_used_at))
                .limit(50)
            )
            entries = db.execute(entries_stmt).scalars().all()
            
            # Update counter kalau istilah tersebut muncul di teks asli
            if original_text and entries:
                updated = False
                for e in entries:
                    if e.original_term in original_text:
                        e.usage_count += 1
                        updated = True
                if updated:
                    db.commit()

            # Bersihkan glossary kalau sudah kebanyakan (limit 100 per thread)
            total_count = db.query(LorebookEntry).filter(LorebookEntry.thread_id == thread_id).count()
            if total_count > 100:
                # Hapus 20 istilah yang jarang dipakai
                cleanup_stmt = (
                    select(LorebookEntry)
                    .where(LorebookEntry.thread_id == thread_id)
                    .order_by(LorebookEntry.usage_count.asc(), LorebookEntry.last_used_at.asc())
                    .limit(20)
                )
                to_delete = db.execute(cleanup_stmt).scalars().all()
                for item in to_delete:
                    db.delete(item)
                db.commit()

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
        Cari bagian 'Translator Notes' di output AI terus simpan istilah barunya ke database.
        Mendukung pemisah kayak :, ->, →, atau —
        """
        import re
        
        # Cari header semacam "Translator Notes:", "Notes:", dsb.
        header_pattern = re.compile(r"(Translator['s]*\s*Notes?[:\s]*|### Translator['s]*\s*Notes?[:\s]*|Notes?[:\s]*)", re.IGNORECASE)
        match = header_pattern.search(full_text)
        
        if not match:
            return

        # Ambil semua teks setelah header tersebut
        notes_section = full_text[match.end():].strip()
        
        lines = notes_section.split("\n")
        new_entries = []
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3: continue
            
            # Cek pakai separator apa
            separator = None
            for sep in ["→", "->", ":", "—"]: 
                if sep in line:
                    separator = sep
                    break
            
            if separator:
                parts = line.split(separator, 1)
                term = parts[0].strip().lstrip("-*• ").strip()
                desc = parts[1].strip()
                
                # Abaikan kalau AI cuma bilang "tidak ada istilah baru"
                skip_keywords = ["not present", "not found", "bukan di bab ini", "tidak ada", "n/a", "unknown"]
                if any(kw in desc.lower() for kw in skip_keywords):
                    continue

                if term and len(term) < 100 and len(term) > 1:
                    term = term.strip('"\'')
                    
                    # Cek dulu biar gak dobel
                    exists_stmt = select(LorebookEntry).where(
                        LorebookEntry.thread_id == thread_id,
                        LorebookEntry.original_term == term
                    )
                    exists = db.execute(exists_stmt).scalar_one_or_none()
                    
                    if not exists:
                        # Pisahkan antara arti translasi sama catatannya (kalau ada tanda kurung)
                        final_translated = desc
                        final_notes = f"Auto-extracted"
                        
                        if "(" in desc and desc.endswith(")"):
                            p_start = desc.rfind("(") 
                            final_translated = desc[:p_start].strip()
                            final_notes = desc[p_start+1:-1].strip()

                        new_entry = LorebookEntry(
                            thread_id=thread_id,
                            original_term=term,
                            translated_term=final_translated,
                            notes=final_notes
                        )
                        db.add(new_entry)
                        new_entries.append(f"{term} -> {final_translated}")
        
        if new_entries:
            db.commit()
            print(f"✅ [LOREBOOK] Simpan {len(new_entries)} istilah baru di thread {thread_id}: {new_entries}")

    @staticmethod
    async def extract_glossary_pass(db: Session, thread_id: int, original_text: str, lm_url: str, model: str | None = None):
        """Dedicated pass to extract names/terms BEFORE translation."""
        from services.ai_provider import AIProvider
        
        sys_prompt = (
            "You are a literary analyst and terminology expert. \n"
            "Task: Extract key names, locations, cultivation techniques, and unique terms from the provided Chinese text.\n"
            "Format your output ONLY as a list of 'Translator Notes' like this:\n"
            "- 原本术语 → Translated Term (Brief context)\n"
            "Example: - 宁凡 → Ning Fan (Main Character)\n"
            "If no important terms, output: 'No new terms found.'"
        )
        
        try:
            ai = AIProvider(lm_url)
            payload = {
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Extract terms from this text:\n\n{original_text[:4000]}"}, # Limit to first 4k chars for extraction
                ],
                "temperature": 0.2,
                "max_tokens": 1000
            }
            if model: payload["model"] = model
            
            response = await ai.chat(payload)
            # Use existing logic to save
            ContextEngine.auto_save_glossary(db, thread_id, response)
            print(f"✨ [AI Extract] Pass completed for thread {thread_id}")
        except Exception as e:
            print(f"⚠️ [AI Extract] Failed: {e}")
