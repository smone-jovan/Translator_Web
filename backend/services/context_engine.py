from sqlalchemy import select
from sqlalchemy.orm import Session
from database import LorebookEntry, Thread, GlobalSetting
from services.hallucination_detector import HallucinationDetector

class ContextEngine:
    """
    Urusan bikin prompt buat LLM biar translasinya gak ngaco dan konsisten sama istilah sebelumnya.
    """

    @staticmethod
    def build_translation_prompt(
        db: Session,
        thread_id: int | None,
        target_lang: str,
        original_text: str | None = None,
        translation_mode: str = "quality"
    ) -> str:
        # Atur bahasa target (Indo atau Inggris)
        is_indo = target_lang.lower() == "indonesian"
        lang_name = "Indonesian" if is_indo else "English"

        # Mode-aware settings
        is_quality = translation_mode == "quality"
        
        guidelines = f"""TRANSLATION TASK - CRITICAL OUTPUT LANGUAGE: You MUST write the final translation of the story in {lang_name} only. No Chinese characters or pinyin allowed in the story output. (Exception: You MAY use Chinese characters in the Translator Notes at the very end if requested).

Role:
You are an expert translator of Chinese web novels (urban / system / transmigration).
You must translate only the chapter body and title provided by the user.
Do not add, remove, or summarize content. **DONT SUMMARY NOR CUT THE CHAPTER**.
Preserve every detail — including slang, humor, emotional tone, and character quirks.

IMPORTANT: Translate ALL story text to {lang_name}. Do NOT output Chinese, do NOT leave raw pinyin in the story.

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

Style:
Use smooth, active, web-novel {lang_name} — vivid, immersive, emotional.
Preserve paragraph breaks where natural — don’t force them.
Avoid machine-like long sentences. Break long Chinese sentences into 2–3 {lang_name} sentences if needed — preserve all meaning.

Chinese Text Handling:
Translate ALL Chinese characters and words to {lang_name} in the story.
Do NOT leave any Chinese characters or raw pinyin in the main story text.

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
If the model produces corrupted hybrid garbage tokens, symbol-noise strings, or broken OCR-like output such as 'Shan! IV% Cold ⑦ Erliu 8 Shui #' or mixed-script junk, you MUST delete that garbage instead of translating or preserving it.
Never output malformed token soup, mixed-script noise, isolated symbol clusters, or analysis phrases pretending to be translation.
"""

        # Tambahkan instruksi Translator Notes jika di mode Quality
        if is_quality:
            guidelines += f"""
**ZERO TOLERANCE**: DO NOT include any term in "Translator Notes" that does not appear in the current chapter text. DO NOT mention terms to say they are "not present". If it's not in the chapter, it MUST NOT be in the notes.
After the chapter, if needed, add a section starting EXACTLY with the phrase "### TRANSLATOR NOTES:" for NEW terms (names, items, etc.) FOUND IN THIS CHAPTER.
**FORMAT**: You MUST use this exact format: '- Original Chinese Term → Translated Term (Brief notes tentang istilah tersebut)'.
Do NOT include terms from the Style Reference examples unless they are in the chapter.
If no new terms, skip.
STOP GENERATING immediately after you finish the Translator Notes list. Do NOT output anything else.
"""
        else:
            guidelines += f"""
Do NOT output any Translator Notes. STOP GENERATING immediately after the story ends. Do NOT output anything else.
"""

        # Gabungkan semua context tambahan (Global & Thread-specific)
        full_prompt = guidelines + "\n\n### ADDITIONAL CONTEXT & KNOWLEDGE\n"
        
        gs_stmt = select(GlobalSetting)
        gs = db.execute(gs_stmt).scalar_one_or_none()
        if gs and gs.global_context:
            gc_trunc = gs.global_context[:1000] + "... (truncated)" if len(gs.global_context) > 1000 else gs.global_context
            full_prompt += f"\n[Global Literary Style]:\n{gc_trunc}\n"

        if thread_id:
            if original_text:
                ContextEngine.reactivate_referenced_archived_terms(db, thread_id, original_text)

            thread_stmt = select(Thread).where(Thread.id == thread_id)
            thread = db.execute(thread_stmt).scalar_one_or_none()
            if thread and thread.thread_context:
                tc_trunc = thread.thread_context[:2000] + "... (truncated)" if len(thread.thread_context) > 2000 else thread.thread_context
                full_prompt += f"\n[Thread-Specific Context]:\n{tc_trunc}\n"

            # Style guide injection (Quality mode only)
            if is_quality and thread and thread.style_guide:
                sg_trunc = thread.style_guide[:1000] + "... (truncated)" if len(thread.style_guide) > 1000 else thread.style_guide
                full_prompt += f"\n[Style Guide for This Novel]:\n{sg_trunc}\n"

            # Mode-aware glossary limit:
            # - Quality: follow global max_context_terms setting (user controls depth)
            # - Fast: locked at 10 (protect local LLMs from context bloat)
            global_limit = gs.max_context_terms if gs else 50
            limit = global_limit if is_quality else min(10, global_limit)
            
            # Ambil istilah aktif (non-archived) yang paling sering dipakai atau yang terbaru biar AI gak overload
            from sqlalchemy import desc
            entries_stmt = (
                select(LorebookEntry)
                .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)
                .order_by(desc(LorebookEntry.usage_count), desc(LorebookEntry.last_used_at))
                .limit(limit)
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

            if entries:
                terms_list = []
                for e in entries:
                    note = e.notes if e.notes else ""
                    if note and len(note) > 150:
                        note = note[:147] + "..."
                    terms_list.append(f"- {e.original_term} → {e.translated_term}" + (f" ({note})" if note else ""))
                
                terms = "\n".join(terms_list)
                full_prompt += f"\n[STRICT GLOSSARY / LOREBOOK - MANDATORY]:\n{terms}\n"

        return full_prompt

    @staticmethod
    def reactivate_referenced_archived_terms(db: Session, thread_id: int, original_text: str) -> int:
        """
        Restore archived lorebook entries when their original term appears again in the
        current chapter text. This keeps long-tail context recoverable without forcing
        users to re-add terms manually.
        """
        if not original_text:
            return 0

        archived_stmt = (
            select(LorebookEntry)
            .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == True)
            .order_by(LorebookEntry.id)
        )
        archived_entries = db.execute(archived_stmt).scalars().all()

        restored_count = 0
        for entry in archived_entries:
            if entry.original_term and entry.original_term in original_text:
                entry.is_archived = False
                restored_count += 1

        if restored_count:
            db.commit()
            ContextEngine.enforce_context_limit(db, thread_id)

        return restored_count

    @staticmethod
    def enforce_context_limit(db: Session, thread_id: int):
        """
        Enforce global max_context_terms limit on active glossary entries of a thread.
        Locked entries are protected. Surplus active entries are archived (is_archived = True)
        and compressed (notes = None) using Least Frequently Used (usage_count ASC)
        with Least Recently Used (last_used_at ASC) as a tiebreaker.
        """
        # 1. Fetch global limit setting
        gs_stmt = select(GlobalSetting)
        gs = db.execute(gs_stmt).scalar_one_or_none()
        limit = gs.max_context_terms if gs else 50

        # 2. Get active entries for this thread
        active_stmt = (
            select(LorebookEntry)
            .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)
            .order_by(LorebookEntry.id)
        )
        active_entries = db.execute(active_stmt).scalars().all()

        if len(active_entries) <= limit:
            return

        # 3. surplus count
        surplus_count = len(active_entries) - limit

        # 4. Filter unlocked active entries
        evictable = [e for e in active_entries if not e.is_locked]

        # 5. Sort by usage_count ASC, then last_used_at/created_at ASC
        def sort_key(e):
            timestamp = e.last_used_at or e.created_at
            timestamp_val = timestamp.timestamp() if timestamp else 0
            return (e.usage_count, timestamp_val, e.id)

        evictable.sort(key=sort_key)

        # 6. Evict top surplus entries
        evict_list = evictable[:surplus_count]
        for entry in evict_list:
            entry.is_archived = True
            entry.notes = None  # Compress by deleting notes context
        db.commit()

    @staticmethod
    def strip_translator_notes(text: str) -> str:
        """
        Bersihkan bagian 'Translator Notes' atau 'Notes' dari teks terjemahan cerita.
        HANYA strip jika section ini ada di akhir teks (bagian terakhir), bukan di tengah.
        Ini mencegah hapus konten cerita yang kebetulan mengandung kata 'Notes'.
        """
        if not text:
            return ""
        import re
        # Pola pencarian header catatan penerjemah (Mencegah false positive dengan Author's Note)
        header_pattern = re.compile(
            r"(\n\s*[-—*_#]*\s*Translato(?:r|ion)['s]*\s*Notes?[:\s]?|\n\s*[-—*_#]*\s*Glossary[:\s]?|\n\s*[-—*_#]*\s*New Terms[:\s]?)", 
            re.IGNORECASE
        )
        
        # Cari semua match, ambil yang TERAKHIR (kemungkinan besar di akhir chapter)
        matches = list(header_pattern.finditer(text))
        if not matches:
            return text
        
        last_match = matches[-1]
        
        # We removed the `match_position < 0.7` check here because some LLMs (like Qwen)
        # hallucinate and restart the story translation AFTER the Translator Notes,
        # putting the notes in the middle of the output text. By always cutting at the last match,
        # we strip both the notes and any trailing hallucination.
        
        cleaned = text[:last_match.start()].strip()
        # Bersihkan sisa-sisa formatting markdown di ujung teks
        while True:
            prev_len = len(cleaned)
            cleaned = cleaned.rstrip(" \t\n\r*•-—#_")
            if len(cleaned) == prev_len:
                break
        return cleaned

    @staticmethod
    def strip_thinking_blocks(text: str) -> str:
        """
        Strip <think>...</think> and <thought>...</thought> blocks from the text.
        For complete blocks: remove the entire block.
        For unclosed blocks: strip from opening tag to the next double-newline (paragraph break),
        NOT to the end of text — the translation content after the thinking block must be preserved.
        """
        if not text:
            return ""
        import re
        # Remove complete think/thought blocks
        text = re.sub(r"<think\b[^>]*>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<thought\b[^>]*>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
        
        # Handle unclosed tags: strip only the thinking section (up to paragraph break), not entire text
        think_idx = text.lower().find("<think")
        if think_idx != -1 and "</think" not in text.lower()[think_idx:]:
            # Find the next double-newline after the unclosed tag (end of thinking section)
            after_tag = text[think_idx:]
            para_break = after_tag.find("\n\n")
            if para_break != -1:
                # Strip from tag to end of thinking section, keep everything after
                text = text[:think_idx] + after_tag[para_break + 2:]
            else:
                # No paragraph break found — strip just the tag line
                tag_end = after_tag.find("\n")
                if tag_end != -1:
                    text = text[:think_idx] + after_tag[tag_end + 1:]
                else:
                    # Tag is at the very end — just remove it
                    text = text[:think_idx]
            
        thought_idx = text.lower().find("<thought")
        if thought_idx != -1 and "</thought" not in text.lower()[thought_idx:]:
            after_tag = text[thought_idx:]
            para_break = after_tag.find("\n\n")
            if para_break != -1:
                text = text[:thought_idx] + after_tag[para_break + 2:]
            else:
                tag_end = after_tag.find("\n")
                if tag_end != -1:
                    text = text[:thought_idx] + after_tag[tag_end + 1:]
                else:
                    text = text[:thought_idx]
            
        return text

    @staticmethod
    def clean_final_translation(text: str, always_hide_thoughts: bool = True) -> str:
        if not text:
            return ""

        cleaned = text
        if always_hide_thoughts:
            cleaned = ContextEngine.strip_thinking_blocks(cleaned)
        
        # Fallback: if stripping thoughts removed EVERYTHING, the AI might have put the translation inside <think>
        if not cleaned.strip():
            cleaned = text

        cleaned = ContextEngine.strip_translator_notes(cleaned)
        
        # Fallback again
        if not cleaned.strip():
            cleaned = text

        cleaned = HallucinationDetector.strip_garbled_hallucination_lines(cleaned)
        
        # Final safety fallback
        if not cleaned.strip():
            cleaned = text

        return cleaned.strip()

    @staticmethod
    def auto_save_glossary(db: Session, thread_id: int, full_text: str):
        """
        Cari bagian 'Translator Notes' di output AI terus simpan istilah barunya ke database.
        Mendukung pemisah kayak :, ->, →, atau —
        """
        import re
        from sqlalchemy import select, func
        
        # Cari header semacam "Translator Notes:", "Translation Notes:", "Glossary:", dsb.
        header_pattern = re.compile(r"([-—*_#]*\s*Translato(?:r|ion)['s]*\s*Notes?[:\s]*|[-—*_#]*\s*Glossary[:\s]*|[-—*_#]*\s*New Terms[:\s]*)", re.IGNORECASE)
        match = header_pattern.search(full_text)
        
        if not match:
            return

        # Ambil semua teks setelah header tersebut
        notes_section = full_text[match.end():].strip()
        
        lines = notes_section.split("\n")
        new_entries = []
        seen_terms = set()
        
        # Kata kunci yang mengindikasikan teks tersebut hanyalah header, instruksi, atau catatan meta dari AI
        garbage_keywords = [
            "final list", "final output", "as requested", "translator note", "translator's note",
            "notes", "summary", "no new terms", "no terms found", "note:", "notes:", "important note",
            "appears to be", "chapter title", "section title", "chapter heading", "author's note"
        ]
        
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
                term = parts[0].strip(" \t\n\r*•-“”\"'")
                term = re.sub(r"\*\*$", "", term).strip(" \t\n\r*•-“”\"'").strip()
                
                desc = parts[1].strip(" \t\n\r*•-“”\"'")
                desc = re.sub(r"\*\*$", "", desc).strip(" \t\n\r*•-“”\"'").strip()
                
                if not term or not desc:
                    continue
                
                # Abaikan kalau AI cuma bilang "tidak ada istilah baru" atau deskripsi kosong
                skip_keywords = ["not present", "not found", "bukan di bab ini", "tidak ada", "n/a", "unknown"]
                if any(kw in desc.lower() for kw in skip_keywords):
                    continue

                # STRICT: Term asli MANDAT harus mengandung setidaknya satu karakter Hanzi (Aksara Mandarin)
                # dan panjangnya tidak boleh lebih dari 30 karakter. Ini 100% mencegah kalimat Bahasa Inggris tersimpan.
                chinese_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
                if not chinese_pattern.search(term) or len(term) > 30:
                    continue

                if len(term) > 1:
                    term_clean = term.lower()
                    
                    # Skip jika term mengandung emoji atau simbol aneh (seperti checklist, tanda seru lingkaran, dll.)
                    if re.match(r"^[\u2700-\u27BF\uE000-\uF8FF\u2011-\u26FF\U00010000-\U0010FFFF]|✅|✔|❌|✨|⭐|◆|◇|■|□|▲|▼", term):
                        continue
                        
                    # Skip jika term merupakan metadata / teks instruksi AI
                    if any(gk in term_clean for gk in garbage_keywords):
                        continue
                        
                    # Cegah duplikasi di dalam respon AI yang sama (internal deduplication)
                    if term_clean in seen_terms:
                        continue
                    seen_terms.add(term_clean)
                    
                    # Cek dulu di basis data biar gak dobel (case-insensitive & trim spaces)
                    exists_stmt = select(LorebookEntry).where(
                        LorebookEntry.thread_id == thread_id,
                        func.lower(func.trim(LorebookEntry.original_term)) == term_clean
                    )
                    exists = db.execute(exists_stmt).scalars().first()
                    
                    if not exists:
                        # Pisahkan antara arti translasi sama catatannya (kalau ada tanda kurung)
                        final_translated = desc
                        final_notes = f"Auto-extracted: {term}"

                        if "(" in desc and desc.endswith(")"):
                            p_start = desc.rfind("(")
                            final_translated = desc[:p_start].strip()
                            final_notes = f"{desc[p_start+1:-1].strip()} (Auto-extracted)"

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
            print(f"[LOREBOOK] Berhasil menyimpan {len(new_entries)} istilah baru untuk utas {thread_id}: {new_entries}")
            ContextEngine.enforce_context_limit(db, thread_id)

    @staticmethod
    async def extract_glossary_pass(db: Session, thread_id: int, original_text: str, lm_url: str, model: str | None = None, target_lang: str = "English"):
        """Dedicated pass to extract names/terms BEFORE translation."""
        from services.ai.factory import AIProviderFactory
        from database import GlobalSetting
        from sqlalchemy import select

        sys_prompt = (
            "You are a literary analyst and terminology expert. \n"
            "Task: Extract key names, locations, cultivation techniques, sects, clans, buildings, and unique terms from the provided Chinese text.\n"
            f"CRITICAL LANGUAGE RULE: ALL output — translated terms, notes, and context descriptions — MUST be written in {target_lang}. NEVER output notes or descriptions in Chinese.\n"
            "MANDATORY RULE FOR CONTEXT/NOTES: Your brief context MUST explicitly explain relationships. If it is a person, state who they are connected to. If it is a place/sect/building, state its location or affiliated faction.\n"
            "Format your output EXACTLY starting with the header '### TRANSLATOR NOTES:', followed by a list like this:\n"
            "### TRANSLATOR NOTES:\n"
            f"- 原本术语 → Translated Term ({target_lang} context explicitly stating relationships/affiliations)\n"
            "Example:\n"
            "### TRANSLATOR NOTES:\n"
            "- 宁凡 → Ning Fan (Main Character, Disciple of Old Demon) \n"
            "- 天云宗 → Heavenly Cloud Sect (Rival sect located in the Northern Region)\n"
            "If no important terms, output: '### TRANSLATOR NOTES:\nNo new terms found.'"
        )
        
        try:
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            sample_size = gs.extract_sample_size if gs else 1000
            
            provider = AIProviderFactory.get_provider(base_url=lm_url, model=model)
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Extract terms from this text:\n\n{original_text[:sample_size]}"},
            ]
            
            response = await provider.chat_completion(messages=messages, temperature=0.2)
            # Use existing logic to save
            ContextEngine.auto_save_glossary(db, thread_id, response)
            print(f"[EXTRACT] AI glossary extraction completed for thread {thread_id}")
        except Exception as e:
            print(f"[WARN] [EXTRACT] AI glossary extraction failed: {e}")

    @staticmethod
    async def extract_relationships_pass(db: Session, thread_id: int, original_text: str, lm_url: str, model: str | None = None, target_lang: str = "English"):
        """Dedicated pass to extract character relationships from source text."""
        from services.ai.factory import AIProviderFactory
        from database import GlobalSetting, CharacterRelationship
        from sqlalchemy import select
        import json
        import re

        sys_prompt = (
            "You are an expert literary analyst mapping out character relationships in a Chinese web novel.\n"
            "Task: Identify any interpersonal relationships, factions, or affiliations between characters mentioned in the text.\n"
            "Format your output STRICTLY as a JSON array of objects, with no markdown formatting or extra text.\n"
            f"CRITICAL: For 'source', 'target', 'type', and 'notes' fields, you MUST write ALL values in {target_lang}. NEVER output Chinese characters in any field. The audience reads {target_lang} only.\n"
            'Example:\n[\n  {"source": "Ning Fan", "target": "Old Demon", "type": "Master & Disciple", "notes": "Ning Fan learns cultivation from the old demon"}\n]\n'
            "If no relationships are found, output an empty array: []"
        )

        try:
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            sample_size = gs.extract_sample_size if gs else 1000

            provider = AIProviderFactory.get_provider(base_url=lm_url, model=model)
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Extract relationships from this text:\n\n{original_text[:sample_size]}"},
            ]

            response = await provider.chat_completion(messages=messages, temperature=0.1)

            # Clean response to find JSON array
            json_str = response.strip()
            # If wrapped in markdown block, extract it
            if json_str.startswith("```json"):
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif json_str.startswith("```"):
                json_str = json_str.split("```")[1].split("```")[0].strip()

            relationships_data = json.loads(json_str)

            if not isinstance(relationships_data, list):
                print(f"[WARN] [RELATIONSHIPS] Expected a JSON list, got {type(relationships_data)}")
                return 0

            new_count = 0
            for item in relationships_data:
                if "source" not in item or "target" not in item or "type" not in item:
                    continue

                src = item["source"].strip()
                tgt = item["target"].strip()
                rel_type = item["type"].strip()
                notes = item.get("notes", "").strip()

                if not src or not tgt or src == tgt:
                    continue

                # Check for duplicates
                exists = db.execute(
                    select(CharacterRelationship).where(
                        CharacterRelationship.thread_id == thread_id,
                        CharacterRelationship.source_term == src,
                        CharacterRelationship.target_term == tgt,
                        CharacterRelationship.relationship_type == rel_type
                    )
                ).scalars().first()

                if not exists:
                    new_rel = CharacterRelationship(
                        thread_id=thread_id,
                        source_term=src,
                        target_term=tgt,
                        relationship_type=rel_type,
                        notes=notes
                    )
                    db.add(new_rel)
                    new_count += 1

            if new_count > 0:
                db.commit()

            print(f"[EXTRACT] Found {new_count} new relationships for thread {thread_id}")
            return new_count

        except Exception as e:
            print(f"[WARN] [RELATIONSHIPS] Extraction failed: {e}")
            return 0
