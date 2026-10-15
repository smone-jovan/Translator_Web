from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json
import re

from sqlalchemy import select, desc
from database import get_db, GlobalSetting, Thread, Chapter, LorebookEntry
from services.ai.factory import AIProviderFactory
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.context_engine import ContextEngine

router = APIRouter(prefix="/api", tags=["Context"])

class ExtractRequest(BaseModel):
    lm_url: str | None = None
    model: str | None = None
    chapter_count: int | None = None
    sample_size: int | None = None

class ExtractedTerm(BaseModel):
    original_term: str
    translated_term: str | None = None
    notes: str | None = None
    gender: str | None = None


def _sample_chapter_text(text: str, sample_size: int) -> str:
    """
    Stratified multi-window chapter sampling (Head 40% + Middle 30% + Tail 30%)
    when chapter length exceeds sample_size, so terms introduced in mid-chapter
    scenes or cliffhangers are captured alongside chapter openings.
    """
    if not text:
        return ""
    if sample_size <= 0 or len(text) <= sample_size:
        return text
    if sample_size < 300:
        return text[:sample_size]

    head_len = int(sample_size * 0.4)
    mid_len = int(sample_size * 0.3)
    tail_len = sample_size - head_len - mid_len

    mid_start = max(head_len, (len(text) - mid_len) // 2)
    tail_start = max(mid_start + mid_len, len(text) - tail_len)

    head_part = text[:head_len].strip()
    mid_part = text[mid_start : mid_start + mid_len].strip()
    tail_part = text[tail_start:].strip()
    return f"{head_part}\n...\n{mid_part}\n...\n{tail_part}"


def _collect_chapter_samples(
    db: Session,
    thread_id: int,
    chapter_count: int,
    sample_size: int,
) -> tuple[str, int]:
    from database import UserBookmark

    bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id)
    bookmark = db.execute(bookmark_stmt).scalars().first()

    start_order = 0
    if bookmark:
        last_ch = db.execute(select(Chapter).where(Chapter.id == bookmark.chapter_id)).scalar_one_or_none()
        if last_ch:
            start_order = last_ch.order

    def _fetch_from(order_val: int):
        stmt = (
            select(Chapter)
            .where(Chapter.thread_id == thread_id, Chapter.order >= order_val)
            .order_by(Chapter.order)
            .limit(chapter_count)
        )
        rows = db.execute(stmt).scalars().all()
        parts = []
        chars = 0
        for ch in rows:
            if ch.content_original:
                sample = _sample_chapter_text(ch.content_original, sample_size)
                parts.append(f"--- Chapter {ch.order + 1}: {ch.title_original} ---\n{sample}")
                chars += len(sample)
        return "\n\n".join(parts), chars

    full_text, total_chars = _fetch_from(start_order)
    if not full_text and start_order > 0:
        full_text, total_chars = _fetch_from(0)
    return full_text, total_chars


@router.post("/threads/{thread_id}/extract-context")
async def extract_thread_context(thread_id: int, req: ExtractRequest, db: Session = Depends(get_db)):
    """Analyze chapter text to extract key terms (names, locations, etc)."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()

    chapter_count = req.chapter_count if req.chapter_count is not None else (gs.extract_chapter_count if gs else 25)
    sample_size = req.sample_size if req.sample_size is not None else (gs.extract_sample_size if gs else 1000)

    full_text, total_chars = _collect_chapter_samples(db, thread_id, chapter_count, sample_size)
    if not full_text:
        return {"terms": []}

    existing_entries = db.execute(
        select(LorebookEntry)
        .where(LorebookEntry.thread_id == thread_id)
        .order_by(desc(LorebookEntry.is_locked), desc(LorebookEntry.usage_count), LorebookEntry.id)
    ).scalars().all()
    existing_orig_set = {
        ContextEngine.normalize_original_term(e.original_term).lower()
        for e in existing_entries
        if e.original_term
    }
    existing_orig_set.update(
        e.original_term.strip().lower() for e in existing_entries if e.original_term
    )

    existing_glossary_block = ""
    if existing_entries:
        sample_existing = [
            f"- {e.original_term} → {e.translated_term}"
            for e in existing_entries[:60]
            if not ContextEngine.is_garbage_lorebook_entry(e.original_term, e.translated_term)
        ]
        if sample_existing:
            existing_glossary_block = (
                "\nEXISTING GLOSSARY (DO NOT RE-EXTRACT THESE TERMS; ALIGN NEW DERIVATIVE TERMS WITH THESE):\n"
                + "\n".join(sample_existing)
                + "\n"
            )

    global_rules = (gs.global_context if gs else "") or ""
    target_lang = gs.target_language if gs else "Indonesian"

    from services.prompt_templates import detect_source_language
    source_lang = detect_source_language(full_text)

    est_tokens = int(150 + (len(global_rules) / 4) + (total_chars * 1.5))

    if source_lang == "Korean":
        pronoun_evidence = "pronouns (그/그녀) or kinship terms (형/누나/오빠/언니)"
        forbidden_lang = "Korean or Chinese"
    elif source_lang == "Japanese":
        pronoun_evidence = "pronouns (彼/彼女) or gendered terms (兄/姉/少年/少女/姫/王子)"
        forbidden_lang = "Japanese or Chinese"
    else:
        pronoun_evidence = "pronouns (他/她) or gendered terms (师兄/师姐/公子/小姐)"
        forbidden_lang = "Chinese"

    prompt = (
        f"You are an expert literary analyst specializing in {source_lang} web novels.\n"
        f"Your task is to identify and extract NEW key proper nouns from the text provided, following these rules:\n\n"
        f"CRITICAL LANGUAGE RULE: ALL output — translated_term AND notes — MUST be written entirely in {target_lang}. NEVER write notes, descriptions, or context in {forbidden_lang}. The audience reads {target_lang} ONLY.\n\n"
        f"RULES & ETHICS (MANDATORY):\n{global_rules}\n"
        f"{existing_glossary_block}\n"
        f"EXTRACTION GUIDELINES:\n"
        f"1. Focus on the MOST FREQUENT and SIGNIFICANT NEW terms (Protagonist, key items, recurring locations, sects/clans/guilds, ranks, buildings/cities) not already in the Existing Glossary.\n"
        f"2. Ignore generic or common words. Only take high-priority proper nouns. Keep 'original_term' as the clean {source_lang} term without parenthetical romanization.\n"
        f"3. Provide: The original {source_lang} term, a natural {target_lang} translation (consistent with Existing Glossary), and brief notes IN {target_lang}.\n"
        f"4. MANDATORY FOR NOTES: The 'notes' MUST be in {target_lang} and MUST explicitly explain the entity's relationship/role (e.g., 'Master of X', 'Capital City of Y Empire', 'Rival Clan to Z'). Be descriptive about connections.\n"
        f"5. GENDER RULE (HUMAN PERSONS ONLY): For human characters ONLY, if their gender is explicitly stated or proven by {pronoun_evidence} in the text, include 'gender': 'MALE' or 'FEMALE'. If uncertain, or if the entity is a place, city, sect, technique, item, or genderless concept, you MUST output 'gender': null. NEVER assign gender to cities, locations, sects, techniques, or objects.\n"
        f"6. Format STRICTLY as a raw JSON list without markdown backticks. Example:\n"
        f'[{{\n  "original_term": "...",\n  "translated_term": "...",\n  "notes": "...",\n  "gender": "MALE" | "FEMALE" | null\n}}]\n'
    )

    ai_url = resolve_active_base_url(gs, req.lm_url)
    selected_model = resolve_active_model(gs, req.model)
    provider = AIProviderFactory.get_provider(base_url=ai_url, model=selected_model, db_session=db)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": full_text},
    ]

    try:
        content = await provider.chat_completion(messages=messages, temperature=0.2)

        thought_process = ""
        thought_match = re.search(r'<(?:thought|think)>(.*?)</(?:thought|think)>', content, flags=re.DOTALL | re.IGNORECASE)
        if thought_match:
            thought_process = thought_match.group(1).strip()
        elif '</thought>' in content.lower():
            idx = content.lower().rfind('</thought>')
            thought_process = content[:idx].strip()
            content = content[idx + len('</thought>'):]
        elif '</think>' in content.lower():
            idx = content.lower().rfind('</think>')
            thought_process = content[:idx].strip()
            content = content[idx + len('</think>'):]

        content = ContextEngine.strip_thinking_blocks(content)
        content = content.replace('```json', '').replace('```', '')

        def build_metadata():
            return {
                "est_input_tokens": est_tokens,
                "total_chars": total_chars,
                "reasoning": thought_process
            }

        def sanitize_terms(terms_list):
            out = []
            seen_batch = set()
            for t in terms_list:
                if not isinstance(t, dict):
                    continue
                raw_orig = str(t.get("original_term") or "").strip()
                orig = ContextEngine.normalize_original_term(raw_orig)
                trans = str(t.get("translated_term") or "").strip()
                notes = str(t.get("notes") or "").strip()
                raw_g = t.get("gender")

                if not orig or not trans:
                    continue
                if ContextEngine.is_garbage_lorebook_entry(orig, trans):
                    continue

                orig_key = orig.lower()
                if orig_key in seen_batch or orig_key in existing_orig_set:
                    continue
                seen_batch.add(orig_key)

                gender = None
                if raw_g and str(raw_g).upper() in ("MALE", "FEMALE"):
                    gender = str(raw_g).upper()
                elif notes:
                    m = re.search(r"\b(MALE|FEMALE)\b\s*[—–-]", notes, re.IGNORECASE)
                    if m:
                        gender = m.group(1).upper()

                if gender and ContextEngine.is_non_human_term(orig, trans, notes):
                    gender = None

                out.append({
                    "original_term": orig,
                    "translated_term": trans,
                    "notes": notes,
                    "gender": gender,
                })
            return out

        # 1. Try to find and parse complete JSON block
        try:
            arr_match = re.search(r"\[\s*\{", content)
            start_idx = arr_match.start() if arr_match else content.find('[')
            end_idx = content.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx+1]
                terms = json.loads(json_str)
                if isinstance(terms, list):
                    return {
                        "terms": sanitize_terms(terms),
                        "metadata": build_metadata()
                    }
        except Exception:
            pass

        # 2. Object-Scoped Relaxed Regex Fallback (extracting keys per {...} block so unquoted null gender never shifts indices)
        manual_terms = []
        for obj_match in re.finditer(r"\{([^{}]+)\}", content, flags=re.DOTALL):
            block = obj_match.group(1)
            orig_m = re.search(r'"original_term"\s*:\s*"((?:[^"\\]|\\.)*)"', block)
            trans_m = re.search(r'"translated_term"\s*:\s*"((?:[^"\\]|\\.)*)"', block)
            notes_m = re.search(r'"notes"\s*:\s*"((?:[^"\\]|\\.)*)"', block)
            gender_m = re.search(r'"gender"\s*:\s*(?:"(MALE|FEMALE)"|(null|None))', block, flags=re.IGNORECASE)
            if orig_m and trans_m:
                manual_terms.append({
                    "original_term": orig_m.group(1).replace('\\"', '"'),
                    "translated_term": trans_m.group(1).replace('\\"', '"'),
                    "notes": notes_m.group(1).replace('\\"', '"') if notes_m else "",
                    "gender": gender_m.group(1).upper() if (gender_m and gender_m.group(1)) else None,
                })

        if manual_terms:
            return {
                "terms": sanitize_terms(manual_terms),
                "metadata": build_metadata()
            }

        # 3. Final Fallback to line parsing
        lines = content.split('\n')
        for line in lines:
            line = line.strip().lstrip("-*•").strip()
            if not line or line.startswith('"'):
                continue
            for sep in ("→", "->", "—", ":"):
                if sep in line:
                    parts = line.split(sep, 1)
                    term = parts[0].strip().strip('"')
                    rhs = parts[1].strip().strip('"')
                    if 1 <= len(term) < 50 and rhs and term.lower() not in ["original_term", "translated_term", "notes", "gender"]:
                        trans_val = rhs
                        notes_val = ""
                        if "(" in rhs and rhs.endswith(")"):
                            p_idx = rhs.rfind("(")
                            trans_val = rhs[:p_idx].strip()
                            notes_val = rhs[p_idx + 1 : -1].strip()
                        manual_terms.append({
                            "original_term": term,
                            "translated_term": trans_val,
                            "notes": notes_val,
                            "gender": None,
                        })
                    break

        return {
            "terms": sanitize_terms(manual_terms),
            "metadata": build_metadata()
        }

    except Exception as e:
        raise HTTPException(502, f"Extraction Parsing Failed: {str(e)}")

@router.post("/threads/{thread_id}/extract-relationships")
async def extract_thread_relationships(thread_id: int, req: ExtractRequest, db: Session = Depends(get_db)):
    """Analyze chapter text to extract character relationships."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()

    chapter_count = req.chapter_count if req.chapter_count is not None else (gs.extract_chapter_count if gs else 25)
    sample_size = req.sample_size if req.sample_size is not None else (gs.extract_sample_size if gs else 1000)

    full_text, _ = _collect_chapter_samples(db, thread_id, chapter_count, sample_size)
    if not full_text:
        return {"status": "ok", "new_count": 0}

    ai_url = resolve_active_base_url(gs, req.lm_url)
    selected_model = resolve_active_model(gs, req.model)
    target_lang = gs.target_language if gs else "Indonesian"

    new_count = await ContextEngine.extract_relationships_pass(
        db=db,
        thread_id=thread_id,
        original_text=full_text,
        lm_url=ai_url,
        model=selected_model,
        target_lang=target_lang,
        max_input_chars=len(full_text),
    )

    return {"status": "ok", "new_count": new_count}
