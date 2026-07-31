from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
import asyncio
import re

from database import get_db, Thread, Chapter, GlobalSetting
from services.ai.factory import AIProviderFactory
from services.prompt_templates import (
    build_title_cleaning_prompt,
    build_synopsis_translation_prompt,
    build_title_translation_prompt
)

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


def parse_chinese_numerals(cn: str) -> int:
    """
    Converts a Chinese numeral string to an Arabic integer.
    Supports both traditional/simplified and standard unit/positional numerals.
    """
    if not cn:
        return 0
    cn = cn.strip()
    
    CN_NUMS = {
        '零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9, '两': 2, '倆': 2
    }
    CN_UNITS = {
        '十': 10, '拾': 10,
        '百': 100, '佰': 100,
        '千': 1000, '仟': 1000,
        '万': 10000, '萬': 10000,
        '亿': 100000000, '億': 100000000
    }
    
    # Check if there are any units
    has_unit = any(char in CN_UNITS for char in cn)
    if not has_unit:
        val_str = ""
        for char in cn:
            if char in CN_NUMS:
                val_str += str(CN_NUMS[char])
        return int(val_str) if val_str else 0

    total = 0
    current_section = 0
    current_value = 0
    
    for char in cn:
        if char in CN_NUMS:
            current_value = CN_NUMS[char]
        elif char in CN_UNITS:
            unit_val = CN_UNITS[char]
            if unit_val == 10000 or unit_val == 100000000:
                section_val = current_section + current_value
                if section_val == 0:
                    section_val = 1
                total += section_val * unit_val
                current_section = 0
                current_value = 0
            else:
                if current_value == 0:
                    current_value = 1
                current_section += current_value * unit_val
                current_value = 0
            
    return total + current_section + current_value


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
            sys_prompt_clean = build_title_cleaning_prompt()
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
            sys_prompt_syn = build_synopsis_translation_prompt(target_lang)
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

    # Auto-detect starting chapter number
    detected_start = 1
    first_ch_stmt = select(Chapter).where(Chapter.thread_id == thread_id).order_by(Chapter.order).limit(1)
    first_ch = db.execute(first_ch_stmt).scalar_one_or_none()
    if first_ch and first_ch.title_original:
        # Strip common volume prefixes like v\d+[-_]? or Volume \d+ (case-insensitive) to prevent matching the volume number
        title_to_parse = re.sub(r'(?i)^(?:vol(?:ume)?\s*\d+[-_.]?\s*|v\d+[-_.]?\s*)', '', first_ch.title_original).strip()
        # Standard Arabic digit patterns first (prioritize chapter markers over volume markers)
        match = re.search(r'(?i)(?:chapter|bab|ch|第)\s*(\d+)', title_to_parse)
        if not match:
            match = re.search(r'(?i)(?:vol|volume)\s*(\d+)', title_to_parse)
        if match:
            detected_start = int(match.group(1))
        else:
            match = re.search(r'\d+', title_to_parse)
            if match:
                detected_start = int(match.group(0))
            else:
                # Chinese numeral patterns (using helper)
                match = re.search(r'(?i)(?:chapter|bab|vol|volume|ch|第)\s*([一二三四五六七八九十百千万零两]+)', title_to_parse)
                if match:
                    detected_start = parse_chinese_numerals(match.group(1))
                else:
                    match = re.search(r'[一二三四五六七八九十百千万零两]+', title_to_parse)
                    if match:
                        detected_start = parse_chinese_numerals(match.group(0))

    start_num_offset = start_number if start_number is not None else detected_start

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
        current_ch = start_num_offset
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
        max_chapter_num = start_num_offset + total_chapters - 1

    titles_to_process = []
    indices = [] # -1 for thread title, >=0 for actual chapter objects

    # If full thread polishing and not specific chapter
    if not chapter_id:
        needs_repolish = any(ord(char) > 127 for char in (thread.title or ""))
        if thread.title and (needs_repolish or repolish):
            # Send the original title if available, otherwise fallback to the current title
            source_title = thread.original_title if thread.original_title else thread.title
            titles_to_process.append(source_title)
            indices.append(-1)

    for i, c in enumerate(chapters):
        # Process if untranslated OR if repolish requested OR if current translation still contains Chinese (when target_lang is not Chinese)
        is_untranslated = not c.title_translated or (target_lang.lower() != "chinese" and contains_chinese(c.title_translated))
        if c.title_original and (is_untranslated or repolish):
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
    total_chunks = (len(titles_to_process) + CHUNK_SIZE - 1) // CHUNK_SIZE

    async def stream_generator():
        nonlocal start_num_offset
        total_count = 0
        
        for start_idx in range(0, len(titles_to_process), CHUNK_SIZE):
            if start_idx > 0 and polish_mode == "soft":
                await asyncio.sleep(1.0) # Breath for LM Studio
                
            chunk_num = start_idx // CHUNK_SIZE + 1
            yield f'{{"status": "processing", "chunk": {chunk_num}, "total": {total_chunks}}}\n'
            
            end_idx = start_idx + CHUNK_SIZE
            chunk_titles = titles_to_process[start_idx:end_idx]
            chunk_indices = indices[start_idx:end_idx]
            
            prompt_lines = []
            for i, title in enumerate(chunk_titles):
                abs_idx = chunk_indices[i]
                label = "BOOK_TITLE" if abs_idx == -1 else f"CHAPTER_{abs_idx}"
                prompt_lines.append(f"[{label}]: {title}")

            sys_prompt = build_title_translation_prompt(target_lang)
            user_prompt = "\n".join(prompt_lines)

            try:
                print(f"🔄 Processing title batch {chunk_num}...")
                provider = AIProviderFactory.get_provider(base_url=lm_url)
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                response = await provider.chat_completion(messages=messages, temperature=0.3)
                translated_lines = [line.strip() for line in response.split("\n") if line.strip()]
                
                for line in translated_lines:
                    match = re.search(r'(BOOK_TITLE|CHAPTER_\d+)[\]\-\:\s]*(.*)', line, re.IGNORECASE)
                    if not match:
                        continue
                        
                    label = match.group(1).upper()
                    translated_title = match.group(2).strip()

                    if "BOOK_TITLE" in label:
                        if -1 in chunk_indices:
                            thread.title = translated_title
                            total_count += 1
                            chunk_indices[chunk_indices.index(-1)] = -999
                    elif "CHAPTER_" in label:
                        try:
                            match = re.search(r"CHAPTER_(\d+)", label)
                            if match:
                                ch_idx = int(match.group(1))
                                if 0 <= ch_idx < len(chapters):
                                    target_ch = chapters[ch_idx]
                                    if volume_mode:
                                        v_num, c_num = chapter_metrics.get(target_ch.id, (start_volume, 1))
                                        formatted_title = clean_and_format_chapter_title(translated_title, c_num, total_chapters, volume_num=v_num)
                                    else:
                                        order_num = start_num_offset + target_ch.order
                                        formatted_title = clean_and_format_chapter_title(translated_title, order_num, max_chapter_num)
                                    target_ch.title_translated = formatted_title
                                    total_count += 1
                        except Exception as e:
                            print(f"⚠️ Skip line '{line}': {e}")
                
                db.commit()
            except Exception as e:
                print(f"❌ Batch Error at chunk {start_idx}: {e}")
                yield f'{{"status": "error", "message": "AI Error at chunk {start_idx}: {str(e)}"}}\n'
                return

        # Sweep and apply volume/sequential formatting to ALL chapters in the thread that have translated titles
        for target_ch in all_chapters:
            if target_ch.title_translated:
                content_preview = (target_ch.content_original or "").strip()
                toc_indicators = ["简介", "目录", "第一章", "第二章", "第三章", "第四章", "第五章", "第六章", "第七章", "第八章", "第九章", "第十章"]
                toc_count = sum(1 for indicator in toc_indicators if indicator in content_preview)
                is_toc_page = len(content_preview) < 5000 and toc_count >= 5
                if is_toc_page:
                    continue

                if volume_mode:
                    v_num, c_num = chapter_metrics.get(target_ch.id, (start_volume, 1))
                    formatted_title = clean_and_format_chapter_title(target_ch.title_translated, c_num, total_chapters, volume_num=v_num)
                else:
                    order_num = start_num_offset + target_ch.order
                    formatted_title = clean_and_format_chapter_title(target_ch.title_translated, order_num, max_chapter_num)
                target_ch.title_translated = formatted_title
        
        db.commit()
        yield f'{{"status": "done", "count": {total_count}}}\n'

    from fastapi.responses import StreamingResponse
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
