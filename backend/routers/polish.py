from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
import asyncio
import re

from database import get_db, Thread, Chapter, GlobalSetting
from services.ai.factory import AIProviderFactory

router = APIRouter(prefix="/api", tags=["Polish"])

def clean_and_format_chapter_title(title: str, order_num: int, total_chapters: int, volume_num: int = None) -> str:
    """
    Cleans chapter title of redundant numbers, prefixes (e.g. Bab, Chapter, Vol, 第几章),
    and formats it in a beautiful zero-padded style (e.g., '01. Title Name', 'V2-01. Title Name').
    """
    t = title.strip()
    
    # 1. Clean out common brackets, quotes, braces at the edges
    t = re.sub(r'^[\'"“«「\[\(\s]+', '', t)
    t = re.sub(r'[\'"”»」\]\)\s]+$', '', t)
    
    # 2. Repeatedly strip common prefixes (nested loop for safety)
    while True:
        prev = t
        # Strip existing volume-aware prefixes like V1-098. or V2. or v1_99:
        t = re.sub(r'(?i)^v\d+[-_]?\d*\s*[\.\-:：~\s]*', '', t).strip()
        # Strip "Chapter X", "Bab X", "Vol X", "Ch X", "Volume X" (case insensitive)
        t = re.sub(r'(?i)^(chapter|bab|vol|volume|ch)\s*\d+\s*[\.\-:：~\s]*', '', t).strip()
        # Strip Chinese chapter prefixes: 第X章 or 第X话 or 第X节 or 第X回 or 第X卷
        t = re.sub(r'^第\s*\d+\s*[章节话回卷节]\s*[\.\-:：~\s]*', '', t).strip()
        # Strip leading numbers with dots, dashes, colons: e.g. "1. ", "01 - ", "12: "
        t = re.sub(r'^\d+\s*[\.\-:：~\s]+\s*', '', t).strip()
        # Strip just leading digits if they are separated by space
        t = re.sub(r'^\d+\s+', '', t).strip()
        
        if t == prev:
            break
            
    # 3. Clean up residual wrapping characters again
    t = re.sub(r'^[\'"“«「\[\(\s]+', '', t)
    t = re.sub(r'[\'"”»」\]\)\s]+$', '', t)

    # 4. Calculate dynamic padding width based on total number of chapters
    width = 2
    if total_chapters >= 1000:
        width = 4
    elif total_chapters >= 100:
        width = 3
        
    # Format
    padded = f"{order_num:0{width}d}"
    if volume_num is not None:
        # User Option A format: V2-01. Title
        if not t:
            return f"V{volume_num}-{padded}. Chapter {order_num}"
        return f"V{volume_num}-{padded}. {t}"
    
    # If the clean title is empty (e.g. original was just "Chapter 12"), fallback to "Chapter {order_num}"
    if not t:
        return f"{padded}. Chapter {order_num}"
    return f"{padded}. {t}"


@router.post("/threads/{thread_id}/translate-titles")
async def translate_titles(
    thread_id: int, 
    target_lang: str = "Indonesian", 
    repolish: bool = False,
    chapter_id: Optional[int] = None,
    start_number: Optional[int] = None,
    volume_mode: bool = Query(False, description="Enable Volume-aware numbering format"),
    auto_detect_volume: bool = Query(False, description="Auto-detect volume boundaries from raw title numbers"),
    start_volume: int = Query(1, description="Starting volume number if no previous volumes exist"),
    volume_boundaries: Optional[str] = Query(None, description="Comma-separated list of chapter numbers where a new volume begins"),
    volume_boundary_type: str = Query("raw", description="Boundary matching type: 'raw' or 'sequence'"),
    chapters_per_volume: Optional[int] = Query(None, description="Fixed number of chapters per volume"),
    db: Session = Depends(get_db)
):
    """Bulk translate or polish titles in a thread."""
    # Get server-side settings
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    lm_url = gs.lm_url if gs else "http://localhost:1234"
    polish_mode = gs.polish_mode if gs else "soft"
    polish_soft_limit = gs.polish_soft_limit if gs else 100

    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    
    if not thread:
        raise HTTPException(404, "Thread not found")

    # Unicode utility to detect Chinese chars
    def contains_chinese(text: str) -> bool:
        if not text:
            return False
        return any('\u4e00' <= char <= '\u9fff' for char in text)

    # Clean thread original title and translate thread synopsis/description if bulk polishing
    if not chapter_id:
        # A. Clean Original Title (ADR-020 Compliance)
        if thread.original_title and contains_chinese(thread.original_title):
            print(f"🔄 [ADR-020] Cleansing original title: {thread.original_title}")
            sys_prompt_clean = (
                "You are an expert Chinese web novel database assistant.\n"
                "Your task is to take a raw, messy Chinese novel title (which may contain extra words, descriptive text, "
                "parentheses, tags, or chapter details) and return ONLY the clean, official Chinese title of the novel.\n"
                "Rules:\n"
                "1. Strip all annotations, brackets like 【】, tags like (无女主) or (轻松) or (变百), and ads.\n"
                "2. Respond with ONLY the cleaned Chinese title characters. Do not include any greeting, markdown, note, or translation.\n"
                "3. If the input is already clean or contains English, return it clean without explaining.\n"
                "Example Input: 我怎么可能是圣女？（无女主，变百，轻松）\n"
                "Example Output: 我怎么可能是圣女？"
            )
            user_prompt_clean = f"Please clean this title: {thread.original_title}"
            try:
                provider = AIProviderFactory.get_provider(base_url=lm_url)
                messages_clean = [
                    {"role": "system", "content": sys_prompt_clean},
                    {"role": "user", "content": user_prompt_clean}
                ]
                cleaned_title = await provider.chat_completion(messages=messages_clean, temperature=0.3)
                cleaned_title = cleaned_title.strip()
                if cleaned_title and len(cleaned_title) < 200:
                    print(f"✅ Cleaned original title to: {cleaned_title}")
                    thread.original_title = cleaned_title
            except Exception as e:
                print(f"⚠️ Failed to clean original_title in translate_titles: {e}")
 
        # B. Translate Synopsis if still in Chinese
        if thread.synopsis and contains_chinese(thread.synopsis):
            print(f"🔄 Translating Chinese synopsis/description...")
            sys_prompt_syn = (
                f"You are a professional literary translator specializing in {target_lang}. "
                "Translate the following novel synopsis/description accurately and elegantly. "
                "Ensure the translation is natural and highly readable, retaining the original meaning and tone."
            )
            user_prompt_syn = thread.synopsis
            try:
                provider = AIProviderFactory.get_provider(base_url=lm_url)
                messages_syn = [
                    {"role": "system", "content": sys_prompt_syn},
                    {"role": "user", "content": user_prompt_syn}
                ]
                translated_syn = await provider.chat_completion(messages=messages_syn, temperature=0.3)
                translated_syn = translated_syn.strip()
                if translated_syn:
                    print(f"✅ Successfully translated synopsis.")
                    thread.synopsis = translated_syn
            except Exception as e:
                print(f"⚠️ Failed to translate synopsis in translate_titles: {e}")
                
        db.commit()

    # Load all chapters for accurate sequence analysis to compute metrics across the entire thread
    ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order)
    all_chapters = db.execute(ch_stmt).scalars().all()

    if not all_chapters:
        return {"count": 0}

    # Filter chapters if polishing a single chapter
    if chapter_id:
        chapters = [c for c in all_chapters if c.id == chapter_id]
    else:
        chapters = all_chapters

    if not chapters:
        return {"count": 0}

    # Count total chapters in the thread for padding width calculation
    total_chapters = len(all_chapters)

    start_num_offset = start_number

    chapter_metrics = {}
    if volume_mode:
        
        # Parse volume boundaries
        vol_boundaries = set()
        if volume_boundaries:
            try:
                vol_boundaries = {int(x.strip()) for x in volume_boundaries.split(",") if x.strip()}
            except Exception:
                pass
        
        current_vol = start_volume
        current_ch = start_num_offset if start_num_offset is not None else 1
        prev_raw_num = 0
        volume_just_incremented = False
        
        for c in all_chapters:
            if not c.title_original:
                chapter_metrics[c.id] = (current_vol, current_ch)
                current_ch += 1
                volume_just_incremented = False
                continue
                
            raw_num = 0
            match = re.search(r'(?i)(?:chapter|bab|vol|volume|ch|第)\s*(\d+)', c.title_original)
            if match:
                raw_num = int(match.group(1))
            else:
                match = re.search(r'\d+', c.title_original)
                if match:
                    raw_num = int(match.group(0))
            
            # Prologue/Epilogue detection
            is_prologue = False
            title_lower = c.title_original.lower()
            prologue_keywords = ["序章", "楔子", "序言", "引子", "prologue", "prelude"]
            if any(kw in title_lower for kw in prologue_keywords):
                is_prologue = True
                    
            # Boundary detection
            is_boundary = False
            if vol_boundaries:
                if volume_boundary_type == "sequence":
                    if (c.order + 1) in vol_boundaries:
                        is_boundary = True
                else: # default to "raw"
                    if raw_num > 0 and raw_num in vol_boundaries:
                        is_boundary = True
                        
            if chapters_per_volume and chapters_per_volume > 0:
                if c.order > 0 and c.order % chapters_per_volume == 0:
                    is_boundary = True
                    
            # Transition application with guard
            if is_boundary:
                current_vol += 1
                current_ch = 1
                volume_just_incremented = True
            elif is_prologue and c.order > 0:
                current_vol += 1
                current_ch = 0
                volume_just_incremented = True
            elif auto_detect_volume and prev_raw_num > 0 and raw_num > 0 and raw_num < prev_raw_num and raw_num < 10:
                if not volume_just_incremented:
                    current_vol += 1
                    current_ch = raw_num
                    volume_just_incremented = True
                else:
                    current_ch = raw_num
                    volume_just_incremented = False
            else:
                volume_just_incremented = False
                
            chapter_metrics[c.id] = (current_vol, current_ch)
            current_ch += 1
            if raw_num > 0:
                prev_raw_num = raw_num
    else:
        detected_start = 1
        first_ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order).limit(1)
        first_ch = db.execute(first_ch_stmt).scalar_one_or_none()
        if first_ch and first_ch.title_original:
            match = re.search(r'(?i)(?:chapter|bab|vol|volume|ch|第)\s*(\d+)', first_ch.title_original)
            if match:
                detected_start = int(match.group(1))
            else:
                match = re.search(r'\d+', first_ch.title_original)
                if match:
                    detected_start = int(match.group(0))
        start_num_offset = start_num_offset if start_num_offset is not None else detected_start
        max_chapter_num = start_num_offset + total_chapters - 1

    titles_to_process = []
    indices = [] # -1 for thread title, >=0 for actual chapter objects

    # If full thread polishing and not specific chapter
    if not chapter_id:
        if thread.title and any(ord(char) > 127 for char in thread.title):
            titles_to_process.append(thread.title)
            indices.append(-1)

    for i, c in enumerate(chapters):
        # Process if untranslated OR if repolish requested
        if c.title_original and (not c.title_translated or repolish):
            titles_to_process.append(c.title_original)
            indices.append(i)

    if not titles_to_process:
        return {"count": 0}

    # If soft load mode is active, limit the number of chapter titles to process
    if not chapter_id and polish_mode == "soft":
        print(f"ℹ️ [SOFT LOAD] Limiting title processing to {polish_soft_limit} items.")
        titles_to_process = titles_to_process[:polish_soft_limit]
        indices = indices[:polish_soft_limit]

    # Chunking logic optimized for ~8000 context window
    CHUNK_SIZE = 50
    total_count = 0
    
    for start_idx in range(0, len(titles_to_process), CHUNK_SIZE):
        if start_idx > 0:
            await asyncio.sleep(1.0) # Breath for LM Studio
            
        end_idx = start_idx + CHUNK_SIZE
        chunk_titles = titles_to_process[start_idx:end_idx]
        chunk_indices = indices[start_idx:end_idx]
        
        prompt_lines = []
        for i, title in enumerate(chunk_titles):
            # We use the relative index within the chunk for the prompt label
            # But the label must match the absolute index in chunk_indices
            abs_idx = chunk_indices[i]
            label = "BOOK_TITLE" if abs_idx == -1 else f"CHAPTER_{abs_idx}"
            prompt_lines.append(f"[{label}]: {title}")

        sys_prompt = (
            f"You are a professional literary editor and translator specializing in {target_lang}. \n"
            "Task: Translate and creatively polish these chapter titles.\n\n"
            "Requirements:\n"
            "1. Maintain EXACT label format (e.g., [BOOK_TITLE]: or [CHAPTER_0]:).\n"
            "2. Titles should feel 'Polished' and 'Cool', not just literal translations.\n"
            "3. Remove excessive Pinyin or redundant chapter numbers if they exist in the text.\n"
            "4. Return one polished title per line."
        )
        user_prompt = "\n".join(prompt_lines)

        try:
            print(f"🔄 Processing title batch {start_idx//CHUNK_SIZE + 1}...")
            provider = AIProviderFactory.get_provider(base_url=lm_url)
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = await provider.chat_completion(messages=messages, temperature=0.3)
            translated_lines = [line.strip() for line in response.split("\n") if line.strip()]
            
            for line in translated_lines:
                if ":" not in line: continue
                # Handle cases where label might have square brackets
                parts = line.split(":", 1)
                label = parts[0].strip()
                translated_title = parts[1].strip()

                if "BOOK_TITLE" in label:
                    thread.title = translated_title
                    total_count += 1
                elif "CHAPTER_" in label:
                    try:
                        # Extract digit from CHAPTER_X
                        match = re.search(r"CHAPTER_(\d+)", label)
                        if match:
                            ch_idx = int(match.group(1))
                            if 0 <= ch_idx < len(chapters):
                                target_ch = chapters[ch_idx]
                                if volume_mode:
                                    v_num, c_num = chapter_metrics.get(target_ch.id, (start_volume, 1))
                                    formatted_title = clean_and_format_chapter_title(
                                        translated_title,
                                        c_num,
                                        total_chapters,
                                        volume_num=v_num
                                    )
                                else:
                                    order_num = start_num_offset + target_ch.order
                                    formatted_title = clean_and_format_chapter_title(
                                        translated_title,
                                        order_num,
                                        max_chapter_num
                                    )
                                target_ch.title_translated = formatted_title
                                total_count += 1
                    except Exception as e:
                        print(f"⚠️ Skip line '{line}': {e}")
            
            db.commit() # Commit each chunk
        except Exception as e:
            print(f"❌ Batch Error at chunk {start_idx}: {e}")
            raise HTTPException(500, f"AI Error at chunk {start_idx}: {str(e)}")

    # Sweep and apply volume/sequential formatting to ALL chapters in the thread that have translated titles
    for target_ch in all_chapters:
        if target_ch.title_translated:
            if volume_mode:
                v_num, c_num = chapter_metrics.get(target_ch.id, (start_volume, 1))
                formatted_title = clean_and_format_chapter_title(
                    target_ch.title_translated,
                    c_num,
                    total_chapters,
                    volume_num=v_num
                )
            else:
                order_num = start_num_offset + target_ch.order
                formatted_title = clean_and_format_chapter_title(
                    target_ch.title_translated,
                    order_num,
                    max_chapter_num
                )
            target_ch.title_translated = formatted_title
    
    db.commit()

    return {"count": total_count}
