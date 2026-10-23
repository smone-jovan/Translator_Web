import re
import json
from datetime import datetime, timezone
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session
from database import LorebookEntry, Thread, GlobalSetting, CharacterRelationship
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

        single_word_meta = {
            "status", "level", "skill", "skills", "system", "chapter", "title", "name",
            "rank", "item", "items", "location", "target", "protagonist", "note", "notes",
            "example", "output", "input", "rule", "rules", "gender", "male", "female",
        }
        if orig_clean in single_word_meta:
            return True

        # 2. Istilah orisinil mengandung kata meta / instruksi AI
        junk_originals = [
            "translator note", "translator's note", "final list", "chapter title",
            "author's note", "important note", "as requested", "see below", "notes", "summary"
        ]
        if any(jo in orig_clean for jo in junk_originals):
            return True

        # 3. Istilah non-Latin (Mandarin / Korea / Jepang) yang tidak diterjemahkan sama sekali (original == translated)
        import re
        east_asian_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\uac00-\ud7a3\u1100-\u11ff\u3040-\u309f\u30a0-\u30ff]")
        if east_asian_pattern.search(orig) and orig == trans:
            return True

        # 4. Istilah hanya berisi angka
        if orig.isdigit() or trans.isdigit():
            return True

        return False

    @staticmethod
    def is_garbage_term(original_term: str | None, translated_term: str | None) -> bool:
        return ContextEngine.is_garbage_lorebook_entry(original_term, translated_term)

    @staticmethod
    def is_non_human_term(
        original_term: str | None,
        translated_term: str | None,
        notes: str | None = None
    ) -> bool:
        """
        Deteksi apakah suatu entri glosarium merupakan entitas non-manusia
        (nama kota, wilayah, sekte, jurus, senjata, benda, pil, formasi, dll.)
        sehingga TIDAK BOLEH diberi atribut gender atau pronoun di context.
        """
        import re

        orig = (original_term or "").strip()
        trans = (translated_term or "").strip()
        note = (notes or "").strip().lower()

        if not orig and not trans and not note:
            return False

        person_role_patterns = [
            r"\b(?:saint|master|disciple|elder|leader|lord|emperor|empress|king|queen|prince|princess|concubine|patriarch|matriarch|cultivator|scholar|monk|priest|assassin|warrior|general|commander|captain|lieutenant|guard|doctor|physician|merchant|blacksmith|alchemist|ancestor|founder|creator|protagonist|antagonist|villain|hero|sister|brother|father|mother|daughter|son|uncle|aunt|cousin|friend|rival|enemy|apprentice|sovereign|duke|duchess|knight|maid|butler|servant)\b",
            r"\b(?:pemimpin|ketua|tetua|guru|murid|raja|ratu|kaisar|permaisuri|pangeran|putri|selir|pendekar|kultivator|cendekiawan|biksu|pendeta|pembunuh|prajurit|panglima|komandan|kapten|penjaga|tabib|dokter|pedagang|pandai besi|alkemis|leluhur|pendiri|pencipta|tokoh|karakter|saudara|saudari|kakak|adik|ayah|ibu|anak|paman|bibi|sepupu|teman|sahabat|musuh|saingan|pelayan|dayang)\b",
            r"(?:宗主|门主|派主|帮主|掌门|教主|楼主|阁主|殿主|城主|皇帝|皇后|王爷|皇子|公主|长老|师尊|师父|师兄|师弟|师姐|师妹|弟子|老祖|先祖|道友|前辈|晚辈|少主|公子|姑娘|夫人|侍女|管家|圣|仙)",
        ]

        non_human_terms = [
            # Lokasi / Wilayah
            r"\b(?:city|town|village|province|county|prefecture|state|district|region|territory|area|realm|continent|ocean|sea|river|lake|mountain|peak|valley|forest|desert|island|capital|palace|hall|pavilion|tower|chamber|courtyard|street|road|manor)\b",
            r"\b(?:kota|desa|kampung|provinsi|kabupaten|wilayah|daerah|area|alam|benua|samudra|laut|sungai|danau|gunung|puncak|lembah|hutan|gurun|pulau|ibu kota|istana|aula|paviliun|menara|kamar|halaman|jalan)\b",
            # Sekte / Organisasi
            r"\b(?:sect|clan|guild|association|alliance|organization|academy|school|temple|monastery|church|faction)\b",
            r"\b(?:sekte|klan|perguruan|asosiasi|aliansi|organisasi|akademi|sekolah|kuil|biara|gereja|faksi)\b",
            # Benda / Senjata / Teknik / Item
            r"\b(?:sword|blade|saber|spear|halberd|staff|bow|arrow|shield|armor|weapon|artifact|treasure|talisman|scroll|manual|technique|skill|art|method|formula|array|formation|pill|elixir|herb|potion|medicine|cauldron|furnace|beast|monster|creature|stone|crystal)\b",
            r"\b(?:pedang|golok|tombak|tongkat|busur|panah|perisai|zirah|senjata|artefak|pusaka|jimat|gulungan|kitab|buku|teknik|jurus|ilmu|metode|formula|formasi|pil|eliksir|ramuan|obat|kuali|tungku|binatang|hewan|monster|makhluk|batu|kristal)\b",
        ]

        is_trans_non_human = any(re.search(pat + r"\s*$", trans, re.IGNORECASE) for pat in non_human_terms)
        is_trans_person = any(re.search(pat + r"\s*$", trans, re.IGNORECASE) for pat in person_role_patterns)

        # Jika berakhiran kata benda/tempat/sekte tanpa kata peran orang (misal "Heavenly Cloud Sect")
        if is_trans_non_human and not is_trans_person:
            return True

        # Jika diawali kata penanda tempat/benda (misal "Kota Beijing", "Sekte Tianyun", "Pedang Pusaka")
        is_trans_prefixed = bool(re.search(r"^(?:kota|desa|sekte|klan|perguruan|gunung|danau|sungai|pedang|teknik|jurus|pil|kitab)\s+", trans, re.IGNORECASE))
        if is_trans_prefixed and not is_trans_person:
            return True

        has_person_role_in_notes = any(re.search(pat, note, re.IGNORECASE) for pat in person_role_patterns)

        # Karakter Mandarin penanda tempat/organisasi/benda di akhir nama (e.g. 宗, 城, 剑, 丹, 诀, 派, 界)
        # Catatan: 林 tidak dimasukkan karena sangat umum sebagai nama orang/marga
        chinese_non_human_suffixes = r"[城市镇省洲山峰江河海湖谷洞宗门派帮阁殿宫塔院剑刀甲丹药鼎诀功法阵符界]$"
        has_orig_person_suffix = bool(re.search(r"[主祖师友辈人老后皇王姬妾儿奴侍生仙圣君客]$", orig))
        if re.search(chinese_non_human_suffixes, orig) and not has_orig_person_suffix and not is_trans_person and not has_person_role_in_notes:
            return True

        # Pola deskripsi/notes yang mendefinisikan benda/tempat/sekte
        # 1. Frasa pembuka definitif yang langsung mengidentifikasi benda/jurus/tempat di notes
        # (meskipun kalimat lanjutannya menyebut 'master' atau 'protagonist', e.g. "A sacred sword forged by the sect master")
        strong_opening_non_human = r"^(?:a|an|the|sebuah|suatu|nama)\s+(?:ancient\s+|sacred\s+|secret\s+|supreme\s+|rare\s+|legendary\s+|signature\s+)?(?:city|town|village|realm|continent|sect|clan|sword|blade|weapon|artifact|treasure|technique|skill|art|manual|formation|array|pill|elixir|herb|potion|pedang|senjata|pusaka|teknik|jurus|kitab|formasi|pil|sekte|klan|kota)\b"
        if re.search(strong_opening_non_human, note, re.IGNORECASE) and not is_trans_person:
            return True

        non_human_notes_patterns = [
            r"\b(?:a|an|the|ancient|imperial|remote|large|small|major|minor)?\s*(?:capital\s+)?(?:city|town|village|province|region|territory|realm|continent|mountain|river|lake|valley|forest|sect|clan|guild|alliance|faction|sword|blade|weapon|artifact|treasure|technique|skill|art|manual|formation|array|pill|herb|medicine|location|place|building)\b",
            r"\b(?:located in|situated in|capital of|capital city|headquarters of|territory of)\b",
            r"\b(?:sebuah|suatu|kota|desa|wilayah|alam|benua|gunung|sungai|danau|lembah|hutan|sekte|klan|aliansi|pedang|senjata|artefak|pusaka|teknik|jurus|kitab|formasi|pil|ramuan|tempat|bangunan|lokasi)\b",
            r"\b(?:terletak di|berlokasi di|ibu kota dari|ibu kota|markas dari|markas besar)\b",
        ]
        is_notes_non_human = any(re.search(pat, note, re.IGNORECASE) for pat in non_human_notes_patterns)

        if is_notes_non_human and not has_person_role_in_notes and not is_trans_person:
            return True

        return False

    @staticmethod
    def detect_source_language(text: str | None) -> str:
        from services.prompt_templates import detect_source_language
        return detect_source_language(text)

    @staticmethod
    def normalize_original_term(raw_term: str | None) -> str:
        """
        Clean list numbering, markdown bold/italic wrappers, and trailing parenthetical
        romanization (when East Asian script is present) from an extracted original_term.
        """
        if not raw_term:
            return ""
        term = str(raw_term).strip(" \t\n\r*•-“”\"'`")
        term = re.sub(r"^\d+[\.\)]\s*", "", term).strip()
        term = re.sub(r"\*\*|__|~~|`", "", term).strip(" \t\n\r*•-“”\"'`")
        east_asian_re = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\uac00-\ud7a3\u1100-\u11ff\u3040-\u309f\u30a0-\u30ff]")
        if east_asian_re.search(term):
            stripped_paren = re.sub(r"\s*[\(\（\[【][^)\）\]】]*[A-Za-z][^)\）\]】]*[\)\）\]】]\s*$", "", term).strip()
            if stripped_paren and east_asian_re.search(stripped_paren):
                term = stripped_paren
        return term.strip()

    @staticmethod
    def build_glossary_hint(db: Session, thread_id: int, text: str, limit: int = 40) -> str:
        """Glossary block for short texts (titles, synopsis): active terms of the thread that
        appear in `text`, locked first. Empty string when nothing matches."""
        if not text:
            return ""
        entries = db.execute(
            select(LorebookEntry)
            .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)  # noqa: E712
            .order_by(desc(LorebookEntry.is_locked), desc(LorebookEntry.usage_count), LorebookEntry.id)
        ).scalars().all()
        matched = [
            e for e in entries
            if e.translated_term and ContextEngine._term_matches_text(e.original_term, text)
        ][:limit]
        if not matched:
            return ""
        lines = [f"- {e.original_term} => {e.translated_term}" for e in matched]
        nl = chr(10)
        header = (
            "[STRICT GLOSSARY - MANDATORY]" + nl
            + "Always render these terms exactly as given, consistent with the book's chapters:" + nl
        )
        return nl + nl + header + nl.join(lines) + nl

    @staticmethod
    def _term_matches_text(original_term: str, text: str) -> bool:
        """
        Check whether any clean variant of a glossary original_term appears in text.
        Strips parenthetical notes BEFORE splitting by '/' so terms like '罗毅 (Luo Yi / Luoyi)'
        cleanly match '罗毅' in the source text.
        """
        if not original_term or not text:
            return False
        if original_term in text:
            return True
        stripped_outer = re.sub(r"\s*[\(\（\[【].*?[\)\）\]】]", "", original_term).strip()
        if stripped_outer and stripped_outer in text:
            return True
        raw_variants = [v.strip() for v in (stripped_outer or original_term).split("/") if v.strip()]
        for rv in raw_variants:
            clean_v = re.sub(r"\s*[\(\（\[【].*?[\)\）\]】]", "", rv).strip()
            if clean_v and (len(clean_v) > 1 or ord(clean_v[0]) > 127):
                if clean_v in text:
                    return True
        return False

    @staticmethod
    def build_translation_prompt(
        db: Session,
        thread_id: int | None,
        target_lang: str,
        original_text: str | None = None,
        translation_mode: str = "quality",
        model: str | None = None,
        limit: int | None = None,
        mode: str | None = None,
        current_chapter_index: int | None = None,
        custom_instructions: str | None = None,
    ) -> str:
        if mode:
            translation_mode = mode

        is_indo = target_lang.lower() == "indonesian"
        lang_name = "Indonesian" if is_indo else "English"
        is_quality = translation_mode == "quality"

        genre = "default"
        if thread_id:
            thread_stmt = select(Thread).where(Thread.id == thread_id)
            thread_obj = db.execute(thread_stmt).scalar_one_or_none()
            if thread_obj:
                genre = detect_primary_genre(thread_obj.genres, thread_obj.tags)

        from services.prompt_templates import detect_source_language
        source_lang = detect_source_language(original_text)

        guidelines = build_core_translation_guidelines(lang_name, genre, source_lang=source_lang)
        guidelines += build_translator_notes_instruction(is_quality, lang_name, source_lang=source_lang)

        full_prompt = guidelines + "\n\n### ADDITIONAL CONTEXT & KNOWLEDGE\n"

        gs_stmt = select(GlobalSetting)
        gs = db.execute(gs_stmt).scalar_one_or_none()

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

            if is_quality and thread and thread.style_guide:
                sg_trunc = thread.style_guide[:sg_max] + "... (truncated)" if len(thread.style_guide) > sg_max else thread.style_guide
                full_prompt += f"\n[Style Guide for This Novel]:\n{sg_trunc}\n"

            if custom_instructions:
                full_prompt += f"\n[Custom Instructions]:\n{custom_instructions}\n"

            global_limit = gs.max_context_terms if (gs and gs.max_context_terms) else 150
            effective_limit = limit if limit is not None else (global_limit if is_quality else min(10, global_limit))

            all_entries_stmt = (
                select(LorebookEntry)
                .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)
                .order_by(
                    desc(LorebookEntry.is_locked),
                    desc(LorebookEntry.usage_count),
                    desc(LorebookEntry.last_used_at),
                    desc(LorebookEntry.id),
                )
            )
            all_entries = db.execute(all_entries_stmt).scalars().all()

            if original_text and all_entries:
                matched_entries = []
                unmatched_entries = []
                updated = False
                now_utc = datetime.now(timezone.utc)
                for e in all_entries:
                    if ContextEngine._term_matches_text(e.original_term, original_text):
                        e.usage_count = (e.usage_count or 0) + 1
                        e.last_used_at = now_utc
                        matched_entries.append(e)
                        updated = True
                    else:
                        unmatched_entries.append(e)
                if updated:
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()

                matched_entries.sort(
                    key=lambda e: (
                        bool(e.is_locked),
                        len(ContextEngine.normalize_original_term(e.original_term)),
                        (e.usage_count or 0),
                        (e.id or 0),
                    ),
                    reverse=True,
                )

                entries = matched_entries[:effective_limit]
                if len(entries) < effective_limit:
                    entries.extend(unmatched_entries[: effective_limit - len(entries)])
            else:
                entries = all_entries[:effective_limit]

            active_translated_names = set()
            if entries:
                terms_list = []
                from services.glossary_lock import extract_pinyin_aliases, CHINESE_CHAR_PATTERN
                gendered_count = 0
                for e in entries:
                    if ContextEngine.is_garbage_lorebook_entry(e.original_term, e.translated_term):
                        continue
                    active_translated_names.add(e.translated_term.strip().lower())
                    note = e.notes if e.notes else ""
                    if note and len(note) > GLOSSARY_NOTE_MAX_CHARS:
                        note = note[:GLOSSARY_NOTE_MAX_CHARS - 3] + "..."

                    term_display = e.original_term
                    if CHINESE_CHAR_PATTERN.search(term_display) and "(" not in term_display:
                        aliases = extract_pinyin_aliases(term_display)
                        spaced_alias = next((a for a in aliases if " " in a and a[0].isupper()), None)
                        if spaced_alias:
                            term_display = f"{term_display} (Pinyin: {spaced_alias})"

                    raw_gender = getattr(e, "gender", None)
                    gender_token = raw_gender if raw_gender in ("MALE", "FEMALE") else None

                    if gender_token and ContextEngine.is_non_human_term(e.original_term, e.translated_term, e.notes):
                        gender_token = None

                    if gender_token:
                        gendered_count += 1

                    paren = ""
                    if gender_token and not re.search(rf"\b{gender_token}\b", note, re.IGNORECASE):
                        paren = f" ({gender_token} — {note})" if note else f" ({gender_token})"
                    elif note:
                        paren = f" ({note})"

                    terms_list.append(f"- {term_display} → {e.translated_term}{paren}")

                if terms_list:
                    terms = "\n".join(terms_list)
                    full_prompt += f"\n[STRICT GLOSSARY / LOREBOOK - MANDATORY]:\n{terms}\n"
                    if gendered_count:
                        if is_indo:
                            full_prompt += (
                                "\n[PRONOUN / GENDER RULES - MANDATORY]: Glossary entries marked MALE "
                                "are male characters — always use masculine titles/kinship/descriptors "
                                "(e.g., Tuan Muda, Putra, Kakak/Saudara Senior, pemuda, pria) and natural Indonesian "
                                "pronouns (dia/ia/-nya). Entries marked FEMALE are female characters — always use "
                                "feminine titles/kinship/descriptors (e.g., Nona Muda, Putri, Kakak/Saudari Senior, "
                                "gadis, wanita). NEVER leak English pronouns (he/she/him/her) and NEVER infer gender "
                                "from name morphology; glossary declarations are authoritative.\n"
                            )
                        else:
                            full_prompt += (
                                "\n[PRONOUN / GENDER RULES - MANDATORY]: Glossary entries marked MALE "
                                "are male characters — always use he/him/his for them. Entries marked "
                                "FEMALE are female — always use she/her/hers. NEVER infer a character's "
                                "gender from the shape of their name; glossary declarations are authoritative.\n"
                            )

            if is_quality:
                try:
                    rels = db.execute(
                        select(CharacterRelationship)
                        .where(CharacterRelationship.thread_id == thread_id)
                        .order_by(desc(CharacterRelationship.id))
                    ).scalars().all()
                    if rels:
                        matched_rels = [
                            r for r in rels
                            if r.source_term.strip().lower() in active_translated_names
                            or r.target_term.strip().lower() in active_translated_names
                        ]
                        selected_rels = (matched_rels or rels)[:15]
                        rel_lines = [
                            f"- {r.source_term} → {r.target_term}: {r.relationship_type}"
                            + (f" ({r.notes})" if r.notes else "")
                            for r in selected_rels
                        ]
                        if rel_lines:
                            full_prompt += "\n[CHARACTER RELATIONSHIPS & HIERARCHY]:\n" + "\n".join(rel_lines) + "\n"
                except Exception:
                    pass

        return full_prompt

    @staticmethod
    def reactivate_referenced_archived_terms(db: Session, thread_id: int, original_text: str) -> int:
        if not original_text:
            return 0

        archived_stmt = (
            select(LorebookEntry)
            .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == True)
            .order_by(LorebookEntry.id)
        )
        archived_entries = db.execute(archived_stmt).scalars().all()

        restored_ids: set[int] = set()
        now_utc = datetime.now(timezone.utc)
        for entry in archived_entries:
            if entry.original_term and ContextEngine._term_matches_text(entry.original_term, original_text):
                entry.is_archived = False
                entry.usage_count = (entry.usage_count or 0) + 1
                entry.last_used_at = now_utc
                if entry.id is not None:
                    restored_ids.add(entry.id)

        if restored_ids:
            db.commit()
            ContextEngine.enforce_context_limit(db, thread_id, protected_ids=restored_ids)

        return len(restored_ids)

    @staticmethod
    def enforce_context_limit(db: Session, thread_id: int, protected_ids: set[int] | None = None):
        gs_stmt = select(GlobalSetting)
        gs = db.execute(gs_stmt).scalar_one_or_none()
        limit = gs.max_context_terms if (gs and gs.max_context_terms) else 150

        active_stmt = (
            select(LorebookEntry)
            .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)
            .order_by(LorebookEntry.id)
        )
        active_entries = db.execute(active_stmt).scalars().all()

        if len(active_entries) <= limit:
            return

        surplus_count = len(active_entries) - limit
        protected = protected_ids or set()

        evictable = [
            e for e in active_entries
            if not e.is_locked and (e.id not in protected)
        ]

        def sort_key(e):
            timestamp = getattr(e, "last_used_at", None) or getattr(e, "created_at", None)
            timestamp_val = timestamp.timestamp() if timestamp else 0
            return (e.usage_count or 0, timestamp_val, e.id or 0)

        evictable.sort(key=sort_key)

        evict_list = evictable[:surplus_count]
        for entry in evict_list:
            entry.is_archived = True
        db.commit()

    @staticmethod
    def strip_translator_notes(text: str) -> str:
        if not text:
            return ""

        cleaned = text.strip()

        start_header_pattern = re.compile(
            r"^(?:[-—*_#]*\s*Translato(?:r|ion)['’]?s?\s*Notes?\s*[:\n]|[-—*_#]*\s*Glossary\s*[:\n]|[-—*_#]*\s*New\s+Terms\s*[:\n]|[-—*_#]*\s*Footnotes?\s*[:\n])",
            re.IGNORECASE,
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
                    if start_header_pattern.match(l_strip + "\n"):
                        continue
                    if l_strip.startswith(("-", "*", "•", "—")) or "→" in l_strip or "->" in l_strip:
                        continue
                    story_start_idx = i
                    break

            if story_start_idx != -1:
                cleaned = "\n".join(lines[story_start_idx:]).strip()
            else:
                return ""

        header_pattern = re.compile(
            r"(?:\n[ \t]*[-—*_#]*[ \t]*(?:Translato(?:r|ion)['’]?s?[ \t]+Notes?|Glossary|New[ \t]+Terms|Footnotes?)(?:[ \t]*:[ \t]*[-—*_#]*|[ \t]+[-—*_#]+)[ \t]*(?:\n|$)|\n[ \t]*###+[ \t]*Translato(?:r|ion)['’]?s?[ \t]+Notes?[ \t]*(?:\n|$)|\n[ \t]*[-—*_#]*[ \t]*Notes?[ \t]*:[ \t]*(?:\n|$))",
            re.IGNORECASE,
        )
        matches = list(header_pattern.finditer(cleaned))
        if matches:
            first_match = matches[0]
            cleaned = cleaned[:first_match.start()].strip()

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
    def strip_ai_conversational_wrappers(text: str) -> str:
        """Strip AI conversational preambles/postambles and stray truncation sentinels."""
        if not text:
            return ""
        import re
        cleaned = text.replace("[[TRUNCATED]]", "").replace("[[PROHIBITED]]", "").strip()
        preamble_re = re.compile(
            r"^(?:sure[,!.]?\s+|tentu[,!.]?\s+|baik[,!.]?\s+)?"
            r"(?:here\s+(?:is|are)\s+the\s+(?:[a-z]+\s+)*translation[^\n]*[:\uff1a]|"
            r"berikut\s+(?:adalah|ini)\s+(?:hasil\s+)?terjemahan[^\n]*[:\uff1a]|"
            r"ini\s+adalah\s+hasil\s+terjemahan[^\n]*[:\uff1a])\s*\n+",
            re.IGNORECASE,
        )
        cleaned = preamble_re.sub("", cleaned, count=1).strip()

        postamble_re = re.compile(
            r"\n+\s*(?:[-\u2014*_]{2,}\s*(?:end\s+of\s+translation|akhir\s+terjemahan)\s*[-\u2014*_]*|"
            r"(?:i\s+hope\s+this\s+translation\s+helps|let\s+me\s+know\s+if\s+you\s+need\s+any\s+(?:further\s+)?adjustments|"
            r"semoga\s+terjemahan\s+ini\s+membantu)[^\n]*)\s*$",
            re.IGNORECASE,
        )
        cleaned = postamble_re.sub("", cleaned).strip()
        return cleaned

    @staticmethod
    def strip_inline_bilingual_notes(text: str) -> str:
        """
        Strip inline dictionary/Pinyin/TL notes injected by LLMs inside prose
        while preserving visual kaomoji like (\u2299_\u2299) and translated stage reactions like (keringat dingin).
        """
        if not text:
            return ""
        import re
        cleaned = re.sub(
            r"\s*\(\s*(?:Pinyin|Hanzi|Kanji|Hangul|Raw|TL|TN|T/N|TL\s*Note|Translator['\u2019]?s?\s*Note|Catatan\s*Penerjemah)\s*[:\uff1a][^)\n]{1,150}\)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s*\[\s*(?:TL|TN|T/N|TL\s*Note|Translator['\u2019]?s?\s*Note|Catatan\s*Penerjemah)\s*[:\uff1a][^\]\n]{1,150}\]",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"(?<=[A-Za-z0-9])\s*\(\s*[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\uac00-\ud7a3\u3040-\u309f\u30a0-\u30ff]{1,25}\s*\)",
            "",
            cleaned,
        )
        return cleaned

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
        cleaned = ContextEngine.strip_ai_conversational_wrappers(cleaned)

        # If stripping translator notes resulted in empty string, it means the output had ONLY translator notes
        # (no actual story translated). We do NOT restore the notes as if they were story prose.
        if not cleaned.strip():
            return ""

        cleaned = HallucinationDetector.strip_repetitive_character_loops(cleaned)
        cleaned = HallucinationDetector.strip_garbled_hallucination_lines(cleaned)
        cleaned = HallucinationDetector.strip_word_soup_hallucinations(cleaned)
        cleaned = ContextEngine.strip_inline_bilingual_notes(cleaned)
        cleaned = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u2060\u2000-\u200a]", "", cleaned)

        return cleaned.strip()

    @staticmethod
    def enforce_glossary_locking(db: Session, thread_id: int | None, text: str) -> str:
        if not text or not thread_id:
            return text
        from services.glossary_lock import build_glossary_lock_rules, apply_glossary_lock

        entries_stmt = (
            select(LorebookEntry)
            .where(LorebookEntry.thread_id == thread_id)
            .order_by(LorebookEntry.is_archived.asc(), desc(LorebookEntry.is_locked), desc(LorebookEntry.usage_count))
        )
        entries = db.execute(entries_stmt).scalars().all()
        if not entries:
            return text

        valid_entries = [e for e in entries if not ContextEngine.is_garbage_lorebook_entry(e.original_term, e.translated_term)]
        rules = build_glossary_lock_rules(valid_entries)
        return apply_glossary_lock(text, rules)

    @staticmethod
    def auto_save_glossary(
        db: Session,
        thread_id: int,
        full_text: str | dict = "",
        chapter_index: int | None = None,
        glossary_data: dict | None = None,
    ):
        if glossary_data is not None:
            data_dict = glossary_data
        elif isinstance(full_text, dict):
            data_dict = full_text
        else:
            data_dict = None

        if data_dict is not None:
            lines = [f"- {k} -> {v}" for k, v in data_dict.items()]
        else:
            if not isinstance(full_text, str) or not full_text:
                return

            cleaned_source = ContextEngine.strip_thinking_blocks(full_text)
            if not cleaned_source.strip():
                cleaned_source = full_text

            header_pattern = re.compile(
                r"(?:^|\n)[ \t]*[-—*_#]*[ \t]*(?:Translato(?:r|ion)['’]?s?[ \t]+Notes?|Glossary|New[ \t]+Terms)(?:[ \t]*:[ \t]*[-—*_#]*|[ \t]+[-—*_#]+|[ \t]*\n)",
                re.IGNORECASE,
            )
            matches = list(header_pattern.finditer(cleaned_source))
            if not matches:
                return
            notes_section = cleaned_source[matches[-1].end():].strip()
            lines = notes_section.split("\n")

        new_entries = []
        created_entry_objs: list[LorebookEntry] = []
        gender_updates = []
        seen_terms = set()
        now_utc = datetime.now(timezone.utc)

        garbage_keywords = [
            "final list", "final output", "as requested", "translator note", "translator's note",
            "notes", "summary", "no new terms", "no terms found", "note:", "notes:", "important note",
            "appears to be", "chapter title", "section title", "chapter heading", "author's note"
        ]

        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue

            separator = None
            for sep in ["→", "->", ":", "—"]:
                if sep in line:
                    separator = sep
                    break

            if separator:
                parts = line.split(separator, 1)
                raw_term = parts[0].strip(" \t\n\r*•-“”\"'")
                raw_term = re.sub(r"^\d+[\.\)]\s*", "", raw_term).strip(" \t\n\r*•-“”\"'")
                raw_term = re.sub(r"\*\*|__", "", raw_term).strip(" \t\n\r*•-“”\"'").strip()

                desc = parts[1].strip(" \t\n\r*•-“”\"'")
                desc = re.sub(r"\*\*$", "", desc).strip(" \t\n\r*•-“”\"'").strip()

                if not raw_term or not desc:
                    continue

                skip_keywords = ["not present", "not found", "bukan di bab ini", "tidak ada", "n/a", "unknown"]
                if any(kw in desc.lower() for kw in skip_keywords):
                    continue

                raw_term_normalized = ContextEngine.normalize_original_term(raw_term)
                subterms = [
                    ContextEngine.normalize_original_term(st)
                    for st in raw_term_normalized.split("/")
                    if ContextEngine.normalize_original_term(st)
                ]
                if not subterms:
                    subterms = [raw_term_normalized]

                for term in subterms:
                    east_asian_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f\u3040-\u309f\u30a0-\u30ff]")
                    has_source_script = bool(east_asian_pattern.search(term))
                    pinyin_pattern = re.compile(
                        r"^[A-Z][a-z]{1,10}(?:-[A-Za-z][a-z]{1,10})?(?:\s+[A-Z][a-z]{1,10}(?:-[A-Za-z][a-z]{1,10})?){1,3}$"
                    )
                    is_valid_pinyin = bool(pinyin_pattern.match(term)) and len(term) <= GLOSSARY_TERM_MAX_LENGTH
                    if not has_source_script and not is_valid_pinyin:
                        continue
                    if len(term) > GLOSSARY_TERM_MAX_LENGTH:
                        continue

                    if len(term) >= GLOSSARY_MIN_TERM_LENGTH:
                        term_clean = term.lower()

                        if re.match(r"^[\u2700-\u27BF\uE000-\uF8FF\u2011-\u26FF\U00010000-\U0010FFFF]|✅|✔|❌|✨|⭐|◆|◇|■|□|▲|▼", term):
                            continue

                        if any(gk in term_clean for gk in garbage_keywords) or ContextEngine.is_garbage_lorebook_entry(term, desc):
                            continue

                        if term_clean in seen_terms:
                            continue
                        seen_terms.add(term_clean)

                        exists_stmt = select(LorebookEntry).where(
                            LorebookEntry.thread_id == thread_id,
                            func.lower(func.trim(LorebookEntry.original_term)) == term_clean
                        )
                        exists = db.execute(exists_stmt).scalars().first()

                        desc_check = desc.rstrip('.!;,。！ ')
                        has_paren = "(" in desc_check and desc_check.endswith(")")
                        p_start = desc_check.rfind("(") if has_paren else -1

                        gender = None
                        if has_paren:
                            ctx = desc_check[p_start + 1:-1].strip()
                            gender_match = re.match(r"\s*(MALE|FEMALE)\s*[—–-]\s*", ctx, re.IGNORECASE)
                            if gender_match:
                                cand_gender = gender_match.group(1).upper()
                                cand_trans = exists.translated_term if exists else desc_check[:p_start].strip()
                                if not ContextEngine.is_non_human_term(term, cand_trans, desc):
                                    gender = cand_gender

                        if not exists:
                            final_translated = desc
                            final_notes = f"Auto-extracted: {term}"

                            if has_paren:
                                final_translated = desc_check[:p_start].strip()
                                final_notes = f"{desc_check[p_start+1:-1].strip()} (Auto-extracted)"

                            final_translated = re.sub(r"\*\*|__", "", final_translated).strip(" \t\n\r*•-“”\"'")

                            if not final_translated or ContextEngine.is_garbage_lorebook_entry(term, final_translated):
                                continue

                            new_entry = LorebookEntry(
                                thread_id=thread_id,
                                original_term=term,
                                translated_term=final_translated,
                                notes=final_notes,
                                gender=gender,
                                usage_count=1,
                                last_used_at=now_utc,
                            )
                            db.add(new_entry)
                            created_entry_objs.append(new_entry)
                            new_entries.append(f"{term} -> {final_translated}")
                        else:
                            if exists.is_archived:
                                exists.is_archived = False
                                exists.usage_count = (exists.usage_count or 0) + 1
                                exists.last_used_at = now_utc
                                created_entry_objs.append(exists)
                            if gender and exists.gender is None:
                                exists.gender = gender
                                gender_updates.append(f"{term} -> {gender}")

        if new_entries or gender_updates or created_entry_objs:
            db.commit()
        if new_entries or created_entry_objs:
            protected_ids = {e.id for e in created_entry_objs if e.id is not None}
            if new_entries:
                print(f"[LOREBOOK] Berhasil menyimpan {len(new_entries)} istilah baru untuk utas {thread_id}: {new_entries}")
            ContextEngine.enforce_context_limit(db, thread_id, protected_ids=protected_ids)
        if gender_updates:
            print(f"[LOREBOOK] Backfill gender {len(gender_updates)} entri untuk utas {thread_id}: {gender_updates}")

    @staticmethod
    async def extract_glossary_pass(
        db: Session,
        thread_id: int,
        original_text: str,
        lm_url: str,
        model: str | None = None,
        target_lang: str = "English",
        max_input_chars: int | None = None,
    ):
        """Dedicated pass to extract names/terms BEFORE translation, aware of existing thread glossary."""
        from services.ai.factory import AIProviderFactory

        source_lang = ContextEngine.detect_source_language(original_text)
        sys_prompt = build_glossary_extraction_prompt(target_lang, source_lang=source_lang)

        try:
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            base_sample_size = gs.extract_sample_size if gs else 1000
            chapter_sample_limit = max_input_chars if max_input_chars is not None else max(base_sample_size * 6, 6000)

            if len(original_text) <= chapter_sample_limit:
                sampled_text = original_text
            else:
                head_n = int(chapter_sample_limit * 0.45)
                mid_n = int(chapter_sample_limit * 0.25)
                tail_n = chapter_sample_limit - head_n - mid_n
                mid_idx = (len(original_text) - mid_n) // 2
                sampled_text = (
                    original_text[:head_n]
                    + "\n...\n"
                    + original_text[mid_idx : mid_idx + mid_n]
                    + "\n...\n"
                    + original_text[-tail_n:]
                )

            existing_entries = db.execute(
                select(LorebookEntry)
                .where(LorebookEntry.thread_id == thread_id)
                .order_by(desc(LorebookEntry.is_locked), desc(LorebookEntry.usage_count), LorebookEntry.id)
                .limit(60)
            ).scalars().all()
            if existing_entries:
                existing_lines = [
                    f"- {e.original_term} → {e.translated_term}"
                    for e in existing_entries
                    if not ContextEngine.is_garbage_lorebook_entry(e.original_term, e.translated_term)
                ]
                if existing_lines:
                    sys_prompt += (
                        "\n\n[EXISTING GLOSSARY — DO NOT RE-EXTRACT THESE TERMS; ALIGN NEW DERIVATIVE TERMS WITH THESE]:\n"
                        + "\n".join(existing_lines)
                    )

            provider = AIProviderFactory.get_provider(base_url=lm_url, model=model, db_session=db)
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Extract NEW terms from this text:\n\n{sampled_text}"},
            ]

            response = await provider.chat_completion(messages=messages, temperature=0.2)
            cleaned_response = ContextEngine.strip_thinking_blocks(response or "")
            ContextEngine.auto_save_glossary(db, thread_id, cleaned_response)
            print(f"[EXTRACT] AI glossary extraction completed for thread {thread_id}")
        except Exception as e:
            print(f"[WARN] [EXTRACT] AI glossary extraction failed: {e}")

    @staticmethod
    async def extract_relationships_pass(
        db: Session,
        thread_id: int,
        original_text: str,
        lm_url: str,
        model: str | None = None,
        target_lang: str = "English",
        max_input_chars: int | None = None,
    ):
        """Dedicated pass to extract character relationships from source text."""
        from services.ai.factory import AIProviderFactory
        from database import GlobalSetting, CharacterRelationship
        from sqlalchemy import select

        source_lang = ContextEngine.detect_source_language(original_text)
        sys_prompt = build_relationship_extraction_prompt(target_lang, source_lang=source_lang)

        try:
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            sample_limit = max_input_chars if max_input_chars is not None else (gs.extract_sample_size if gs else 1000)

            provider = AIProviderFactory.get_provider(base_url=lm_url, model=model, db_session=db)
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Extract relationships from this text:\n\n{original_text[:sample_limit]}"},
            ]

            response = await provider.chat_completion(messages=messages, temperature=0.1)

            # Strip thinking blocks (<think> / <thought>) and markdown fences before JSON parsing
            cleaned = ContextEngine.strip_thinking_blocks(response or "").strip()
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

            start_idx = cleaned.find("[")
            end_idx = cleaned.rfind("]")
            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                json_str = cleaned[start_idx : end_idx + 1]
            else:
                json_str = cleaned

            relationships_data = json.loads(json_str)

            if not isinstance(relationships_data, list):
                print(f"[WARN] [RELATIONSHIPS] Expected a JSON list, got {type(relationships_data)}")
                return 0

            new_count = 0
            for item in relationships_data:
                if not isinstance(item, dict):
                    continue
                if "source" not in item or "target" not in item or "type" not in item:
                    continue

                src = str(item["source"] or "").strip()
                tgt = str(item["target"] or "").strip()
                rel_type = str(item["type"] or "").strip()
                notes = str(item.get("notes") or "").strip()

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
            print(f"[WARN] [RELATIONSHIPS] AI relationship extraction failed: {e}")
            return 0
