import re
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import LorebookEntry, Thread, GlobalSetting
from services.hallucination_detector import HallucinationDetector
from services.fidelity_checker import verify_translation_fidelity
from services.prompt_templates import (
    build_core_translation_guidelines,
    build_translator_notes_instruction,
    build_glossary_extraction_prompt,
    build_relationship_extraction_prompt,
    detect_primary_genre,
    GLOBAL_CONTEXT_MAX_CHARS,
    THREAD_CONTEXT_MAX_CHARS,
    STYLE_GUIDE_MAX_CHARS,
    GLOSSARY_NOTE_MAX_CHARS,
    GLOSSARY_TERM_MAX_LENGTH,
    GLOSSARY_MIN_TERM_LENGTH,
)
from services.ai.settings import get_context_scale_for_model

class ContextEngine:
    """
    Urusan bikin prompt buat LLM biar translasinya gak ngaco dan konsisten sama istilah sebelumnya.
    """

    @staticmethod
    def is_garbage_lorebook_entry(original_term: str | None, translated_term: str | None) -> bool:
        """
        Deteksi apakah entri glosarium tergolong berkualitas rendah / ampas.
        Mengembalikan True jika entri harus diabaikan/disaring dari context prompt dan database.
        """
        if not original_term or not translated_term:
            return True

        orig = original_term.strip()
        trans = translated_term.strip()

        if not orig or not trans:
            return True

        orig_clean = orig.lower()
        trans_clean = trans.lower()

        # 1. Istilah terjemahan berupa teks placeholder / junk
        junk_translations = {
            "n/a", "none", "unknown", "null", "undefined", "no new terms",
            "not specified", "not present", "not found", "no translation",
            "same as original", "same", "no change", "tidak ada", "bukan di bab ini",
            "context required", "no terms found", "untranslated", "n / a", "n/a."
        }
        if trans_clean in junk_translations or any(jk in trans_clean for jk in ["no new terms", "no terms found", "not specified"]):
            return True

        # 2. Istilah orisinil mengandung kata meta / instruksi AI
        junk_originals = [
            "translator note", "translator's note", "final list", "chapter title",
            "author's note", "important note", "as requested", "see below", "notes", "summary"
        ]
        if any(jo in orig_clean for jo in junk_originals):
            return True

        # 3. Istilah Mandarin yang tidak diterjemahkan sama sekali (original == translated)
        import re
        chinese_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
        if chinese_pattern.search(orig) and orig == trans:
            return True

        # 4. Istilah hanya berisi angka
        if orig.isdigit() or trans.isdigit():
            return True

        return False

    @staticmethod
    def build_translation_prompt(
        db: Session,
        thread_id: int | None,
        target_lang: str,
        original_text: str | None = None,
        translation_mode: str = "quality",
        model: str | None = None
    ) -> str:
        # Atur bahasa target (Indo atau Inggris)
        is_indo = target_lang.lower() == "indonesian"
        lang_name = "Indonesian" if is_indo else "English"

        # Mode-aware settings
        is_quality = translation_mode == "quality"

        # Detect genre from thread (ADR-071)
        genre = "default"
        if thread_id:
            thread_stmt = select(Thread).where(Thread.id == thread_id)
            thread_obj = db.execute(thread_stmt).scalar_one_or_none()
            if thread_obj:
                genre = detect_primary_genre(thread_obj.genres, thread_obj.tags)

        # Build core guidelines from centralized templates (ADR-074)
        guidelines = build_core_translation_guidelines(lang_name, genre)

        # Tambahkan instruksi Translator Notes berdasarkan mode
        guidelines += build_translator_notes_instruction(is_quality, lang_name)

        # Gabungkan semua context tambahan (Global & Thread-specific)
        full_prompt = guidelines + "\n\n### ADDITIONAL CONTEXT & KNOWLEDGE\n"
        
        gs_stmt = select(GlobalSetting)
        gs = db.execute(gs_stmt).scalar_one_or_none()

        # Model-aware context scaling (ADR-075)
        scale = get_context_scale_for_model(model)
        gc_max = int(GLOBAL_CONTEXT_MAX_CHARS * scale)
        tc_max = int(THREAD_CONTEXT_MAX_CHARS * scale)
        sg_max = int(STYLE_GUIDE_MAX_CHARS * scale)

        if gs and gs.global_context:
            gc_trunc = gs.global_context[:gc_max] + "... (truncated)" if len(gs.global_context) > gc_max else gs.global_context
            full_prompt += f"\n[Global Literary Style]:\n{gc_trunc}\n"

        if thread_id:
            if original_text:
                ContextEngine.reactivate_referenced_archived_terms(db, thread_id, original_text)

            thread_stmt = select(Thread).where(Thread.id == thread_id)
            thread = db.execute(thread_stmt).scalar_one_or_none()
            if thread and thread.thread_context:
                tc_trunc = thread.thread_context[:tc_max] + "... (truncated)" if len(thread.thread_context) > tc_max else thread.thread_context
                full_prompt += f"\n[Thread-Specific Context]:\n{tc_trunc}\n"

            # Style guide injection (Quality mode only)
            if is_quality and thread and thread.style_guide:
                sg_trunc = thread.style_guide[:sg_max] + "... (truncated)" if len(thread.style_guide) > sg_max else thread.style_guide
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
                    if ContextEngine.is_garbage_lorebook_entry(e.original_term, e.translated_term):
                        continue
                    note = e.notes if e.notes else ""
                    if note and len(note) > GLOSSARY_NOTE_MAX_CHARS:
                        note = note[:GLOSSARY_NOTE_MAX_CHARS - 3] + "..."
                    terms_list.append(f"- {e.original_term} → {e.translated_term}" + (f" ({note})" if note else ""))
                
                if terms_list:
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
        Bersihkan bagian 'Translator Notes', 'Notes', dan 'Footnotes' dari teks terjemahan cerita
        sehingga pengguna mendapatkan teks prosa murni 100%.
        Mendukung pembersihan catatan baik di akhir, tengah, maupun di awal teks (jika AI salah urutan).
        """
        if not text:
            return ""
        import re

        cleaned = text.strip()

        # 1. Cek apakah ada catatan penerjemah di AWAL teks (sebelum cerita)
        start_header_pattern = re.compile(
            r"^(?:[-—*_#]*\s*Translato(?:r|ion)['s]*\s*Notes?[:\s]*|[-—*_#]*\s*Glossary[:\s]*|[-—*_#]*\s*New Terms[:\s]*|[-—*_#]*\s*Footnotes?[:\s]*)", 
            re.IGNORECASE
        )
        if start_header_pattern.match(cleaned):
            lines = cleaned.split("\n")
            story_start_idx = -1
            in_notes_header = True

            for i, line in enumerate(lines):
                l_strip = line.strip()
                if not l_strip:
                    continue
                if in_notes_header:
                    if start_header_pattern.match(l_strip):
                        continue
                    if l_strip.startswith(("-", "*", "•", "—")) or "→" in l_strip or "->" in l_strip:
                        continue
                    story_start_idx = i
                    break

            if story_start_idx != -1:
                cleaned = "\n".join(lines[story_start_idx:]).strip()
            else:
                # Teks HANYA berisi catatan penerjemah tanpa ada cerita
                return ""

        # 2. Cek apakah ada catatan penerjemah di AKHIR / TENGAH teks (setelah cerita)
        header_pattern = re.compile(
            r"(\n\s*[-—*_#]*\s*Translato(?:r|ion)['s]*\s*Notes?[:\s]?|\n\s*[-—*_#]*\s*Glossary[:\s]?|\n\s*[-—*_#]*\s*New Terms[:\s]?|\n\s*[-—*_#]*\s*Footnotes?[:\s]?)", 
            re.IGNORECASE
        )
        matches = list(header_pattern.finditer(cleaned))
        if matches:
            first_match = matches[0]
            cleaned = cleaned[:first_match.start()].strip()

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
        
        # If stripping translator notes resulted in empty string, it means the output had ONLY translator notes
        # (no actual story translated). We do NOT restore the notes as if they were story prose.
        if not cleaned.strip():
            return ""

        cleaned = HallucinationDetector.strip_garbled_hallucination_lines(cleaned)
        cleaned = HallucinationDetector.strip_word_soup_hallucinations(cleaned)
        cleaned = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u2060\u2000-\u200a]", "", cleaned)
        
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
                raw_term = parts[0].strip(" \t\n\r*•-“”\"'")
                raw_term = re.sub(r"\*\*$", "", raw_term).strip(" \t\n\r*•-“”\"'").strip()
                
                desc = parts[1].strip(" \t\n\r*•-“”\"'")
                desc = re.sub(r"\*\*$", "", desc).strip(" \t\n\r*•-“”\"'").strip()
                
                if not raw_term or not desc:
                    continue
                
                # Abaikan kalau AI cuma bilang "tidak ada istilah baru" atau deskripsi kosong
                skip_keywords = ["not present", "not found", "bukan di bab ini", "tidak ada", "n/a", "unknown"]
                if any(kw in desc.lower() for kw in skip_keywords):
                    continue

                # Dukung pemisahan term berganda dengan garis miring (e.g. 夏茵 / 夏恩 / 莎恩 -> Shain)
                subterms = [st.strip(" \t\n\r*•-“”\"'") for st in raw_term.split("/") if st.strip(" \t\n\r*•-“”\"'")]
                if not subterms:
                    subterms = [raw_term]

                for term in subterms:
                    # Term asli MANDAT harus mengandung setidaknya satu karakter Hanzi (Aksara Mandarin)
                    # ATAU merupakan pinyin term yang valid (2+ Latin words, maks 30 chars).
                    # Ini mencegah kalimat Bahasa Inggris panjang tersimpan, tapi mengizinkan
                    # nama-nama pinyin seperti "Ye Xiu", "Meng Hao" (penting untuk konsistensi novel kelas atas).
                    chinese_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
                    has_chinese = chinese_pattern.search(term)
                    # Pinyin heuristic: 2-4 short words, each capitalized, total <= 30 chars
                    pinyin_pattern = re.compile(r"^[A-Z][a-z]{0,8}(\s[A-Z][a-z]{0,8}){0,3}$")
                    is_valid_pinyin = bool(pinyin_pattern.match(term)) and len(term) <= GLOSSARY_TERM_MAX_LENGTH
                    if not has_chinese and not is_valid_pinyin:
                        continue
                    if len(term) > GLOSSARY_TERM_MAX_LENGTH:
                        continue

                    if len(term) >= GLOSSARY_MIN_TERM_LENGTH:
                        term_clean = term.lower()
                        
                        # Skip jika term mengandung emoji atau simbol aneh (seperti checklist, tanda seru lingkaran, dll.)
                        if re.match(r"^[\u2700-\u27BF\uE000-\uF8FF\u2011-\u26FF\U00010000-\U0010FFFF]|✅|✔|❌|✨|⭐|◆|◇|■|□|▲|▼", term):
                            continue
                            
                        # Skip jika term merupakan metadata / teks instruksi AI atau ampas
                        if any(gk in term_clean for gk in garbage_keywords) or ContextEngine.is_garbage_lorebook_entry(term, desc):
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

                            # Strip trailing punctuation sebelum cek kurung tutup
                            desc_check = desc.rstrip('.!;,。！ ')
                            if "(" in desc_check and desc_check.endswith(")"):
                                p_start = desc_check.rfind("(")
                                final_translated = desc_check[:p_start].strip()
                                final_notes = f"{desc_check[p_start+1:-1].strip()} (Auto-extracted)"

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

        sys_prompt = build_glossary_extraction_prompt(target_lang)
        
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

        sys_prompt = build_relationship_extraction_prompt(target_lang)

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
