from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json
import re

from sqlalchemy import select
from database import get_db, GlobalSetting, Thread, Chapter
from services.ai.factory import AIProviderFactory

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

@router.post("/threads/{thread_id}/extract-context")
async def extract_thread_context(thread_id: int, req: ExtractRequest, db: Session = Depends(get_db)):
    """Analyze chapter text to extract key terms (names, locations, etc)."""
    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    # 1. Identify starting point (last_read or first chapter)
    from database import UserBookmark
    bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id)
    bookmark = db.execute(bookmark_stmt).scalars().first()
    
    start_order = 0
    if bookmark:
        last_ch_stmt = select(Chapter).where(Chapter.id == bookmark.chapter_id)
        last_ch = db.execute(last_ch_stmt).scalar_one_or_none()
        if last_ch:
            start_order = last_ch.order

    # 1.5 Get Global Settings for Defaults
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    
    chapter_count = req.chapter_count if req.chapter_count is not None else (gs.extract_chapter_count if gs else 25)
    sample_size = req.sample_size if req.sample_size is not None else (gs.extract_sample_size if gs else 1000)

    # 2. Fetch up to X chapters starting from start_order
    ch_stmt = (
        select(Chapter)
        .where(Chapter.thread_id == thread_id, Chapter.order >= start_order)
        .order_by(Chapter.order)
        .limit(chapter_count)
    )
    chapters = db.execute(ch_stmt).scalars().all()
    
    if not chapters:
        return {"terms": []}

    # 3. Combine text samples from all fetched chapters
    text_parts = []
    total_chars = 0
    for ch in chapters:
        if ch.content_original:
            sample = ch.content_original[:sample_size]
            text_parts.append(f"--- Chapter {ch.order + 1}: {ch.title_original} ---\n{sample}")
            total_chars += len(sample)
    
    full_text = "\n\n".join(text_parts)
    if not full_text:
        return {"terms": []}

    # 4. Use Global Settings for Prompt
    global_rules = (gs.global_context if gs else "") or ""
    target_lang = gs.target_language if gs else "Indonesian"

    # Estimated tokens (Chinese characters average ~1.5 tokens per character in Qwen/Llama-3 tokenizers)
    # plus static instructions prompt (~150 tokens) and global rules (~0.25 tokens per char)
    est_tokens = int(150 + (len(global_rules) / 4) + (total_chars * 1.5))
    
    prompt = (
        f"You are an expert literary analyst specializing in Chinese web novels.\n"
        f"Your task is to identify and extract key proper nouns from the text provided, following these rules:\n\n"
        f"CRITICAL LANGUAGE RULE: ALL output — translated_term AND notes — MUST be written entirely in {target_lang}. NEVER write notes, descriptions, or context in Chinese. The audience reads {target_lang} ONLY.\n\n"
        f"RULES & ETHICS (MANDATORY):\n{global_rules}\n\n"
        f"EXTRACTION GUIDELINES:\n"
        f"1. Focus on the MOST FREQUENT and SIGNIFICANT terms (Protagonist, key items, recurring locations, sects/clans, buildings/cities).\n"
        f"2. Ignore generic or common words. Only take high-priority patterns.\n"
        f"3. Provide: The original Chinese term, a natural {target_lang} translation, and brief notes IN {target_lang}.\n"
        f"4. MANDATORY FOR NOTES: The 'notes' MUST be in {target_lang} and MUST explicitly explain the entity's relationship/role (e.g., 'Master of X', 'Capital City of Y Empire', 'Rival Clan to Z'). Be descriptive about connections.\n"
        f"5. Format STRICTLY as a raw JSON list without markdown backticks. Example:\n"
        f'[{{\n  "original_term": "...",\n  "translated_term": "...",\n  "notes": "..."\n}}]\n'
    )
    
    ai_url = req.lm_url or (gs.lm_url if gs else "http://localhost:1234")
    provider = AIProviderFactory.get_provider(base_url=ai_url, model=req.model)
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": full_text},
    ]
    
    try:
        content = await provider.chat_completion(messages=messages, temperature=0.2)
        
        # 0. Clean and capture reasoning blocks
        thought_process = ""
        thought_match = re.search(r'<(?:thought|think)>(.*?)</(?:thought|think)>', content, flags=re.DOTALL)
        if thought_match:
            thought_process = thought_match.group(1).strip()
            
        # Also capture if the opening tag was missing but the closing tag exists
        elif '</thought>' in content:
            parts = content.split('</thought>')
            thought_process = parts[0].strip()
            content = parts[-1]
        elif '</think>' in content:
            parts = content.split('</think>')
            thought_process = parts[0].strip()
            content = parts[-1]

        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Strip markdown formatting
        content = content.replace('```json', '').replace('```', '')
        
        # Helper to build metadata
        def build_metadata():
            return {
                "est_input_tokens": est_tokens,
                "total_chars": total_chars,
                "reasoning": thought_process
            }

        # Robust parsing logic
        # 1. Try to find and parse complete JSON block
        try:
            start_idx = content.find('[')
            end_idx = content.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx+1]
                terms = json.loads(json_str)
                return {
                    "terms": terms, 
                    "metadata": build_metadata()
                }
        except:
            pass

        # 2. Advanced Relaxed Regex Fallback (extracting keys individually)
        # This handles cut-off JSON, missing brackets, missing commas, etc.
        manual_terms = []
        originals = re.findall(r'"original_term"\s*:?\s*"([^"]+)"', content)
        translateds = re.findall(r'"translated_term"\s*:?\s*"([^"]+)"', content)
        notes = re.findall(r'"notes"\s*:?\s*"([^"]+)"', content)
        
        if originals:
            for i in range(len(originals)):
                manual_terms.append({
                    "original_term": originals[i],
                    "translated_term": translateds[i] if i < len(translateds) else "",
                    "notes": notes[i] if i < len(notes) else ""
                })
            return {
                "terms": manual_terms, 
                "metadata": build_metadata()
            }

        # 3. Final Fallback to line parsing (if completely unformatted)
        lines = content.split('\n')
        for line in lines:
            line = line.strip().lstrip("-*•").strip()
            if ":" in line and not line.startswith('"'):
                parts = line.split(":", 1)
                term = parts[0].strip().strip('"')
                if len(term) < 50 and term and term.lower() not in ["original_term", "translated_term", "notes"]:
                    manual_terms.append({
                        "original_term": term,
                        "translated_term": "", # Placeholder if manual fallback fails
                        "notes": parts[1].strip().strip('"')
                    })
        
        return {
            "terms": manual_terms,
            "metadata": build_metadata()
        }

    except Exception as e:
        raise HTTPException(502, f"Extraction Parsing Failed: {str(e)}")

@router.post("/threads/{thread_id}/extract-relationships")
async def extract_thread_relationships(thread_id: int, req: ExtractRequest, db: Session = Depends(get_db)):
    """Analyze chapter text to extract character relationships."""
    from services.context_engine import ContextEngine

    stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    # 1. Identify starting point
    from database import UserBookmark
    bookmark_stmt = select(UserBookmark).where(UserBookmark.thread_id == thread_id)
    bookmark = db.execute(bookmark_stmt).scalars().first()

    start_order = 0
    if bookmark:
        last_ch_stmt = select(Chapter).where(Chapter.id == bookmark.chapter_id)
        last_ch = db.execute(last_ch_stmt).scalar_one_or_none()
        if last_ch:
            start_order = last_ch.order

    # 1.5 Get Global Settings
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()

    chapter_count = req.chapter_count if req.chapter_count is not None else (gs.extract_chapter_count if gs else 25)
    sample_size = req.sample_size if req.sample_size is not None else (gs.extract_sample_size if gs else 1000)

    # 2. Fetch up to X chapters starting from start_order
    ch_stmt = (
        select(Chapter)
        .where(Chapter.thread_id == thread_id, Chapter.order >= start_order)
        .order_by(Chapter.order)
        .limit(chapter_count)
    )
    chapters = db.execute(ch_stmt).scalars().all()

    if not chapters:
        return {"status": "ok", "new_count": 0}

    # 3. Combine text samples
    text_parts = []
    for ch in chapters:
        if ch.content_original:
            sample = ch.content_original[:sample_size]
            text_parts.append(f"--- Chapter {ch.order + 1}: {ch.title_original} ---\n{sample}")

    full_text = "\n\n".join(text_parts)
    if not full_text:
        return {"status": "ok", "new_count": 0}

    ai_url = req.lm_url or (gs.lm_url if gs else "http://localhost:1234")
    target_lang = gs.target_language if gs else "Indonesian"

    new_count = await ContextEngine.extract_relationships_pass(
        db=db,
        thread_id=thread_id,
        original_text=full_text,
        lm_url=ai_url,
        model=req.model,
        target_lang=target_lang
    )

    return {"status": "ok", "new_count": new_count}
