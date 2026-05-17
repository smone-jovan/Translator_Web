import sqlite3
import re
import asyncio
import sys

# Reconfigure stdout to use UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def test_volume_mode_logic():
    conn = sqlite3.connect("backend/app.db")
    cursor = conn.cursor()
    
    # 1. Fetch thread and chapters in thread 5
    thread_id = 5
    cursor.execute("SELECT id, title, original_title FROM threads WHERE id = ?", (thread_id,))
    thread = cursor.fetchone()
    print("Thread:", thread)
    
    cursor.execute(
        "SELECT id, `order`, title_original, title_translated FROM chapters WHERE thread_id = ? ORDER BY id",
        (thread_id,)
    )
    chapters = cursor.fetchall()
    print(f"Total chapters: {len(chapters)}")
    
    # Let's run the exact volume detection logic from threads.py:
    volume_mode = True
    auto_detect_volume = True
    start_volume = 1
    start_num_offset = None
    
    chapter_metrics = {}
    current_vol = start_volume
    # If start_num_offset is None, we detect it from first chapter:
    first_title = chapters[0][2]
    match = re.search(r'(?i)(?:chapter|bab|vol|volume|ch|第)\s*(\d+)', first_title)
    if match:
        detected_start = int(match.group(1))
    else:
        match = re.search(r'\d+', first_title)
        if match:
            detected_start = int(match.group(0))
        else:
            detected_start = 1
            
    start_num_offset = start_num_offset if start_num_offset is not None else detected_start
    current_ch = start_num_offset
    prev_raw_num = 0
    
    print("\nTracing Volume Boundary Detection:")
    for ch_id, ch_order, title_orig, title_trans in chapters:
        if not title_orig:
            chapter_metrics[ch_id] = (current_vol, current_ch)
            current_ch += 1
            continue
            
        raw_num = 0
        match = re.search(r'(?i)(?:chapter|bab|vol|volume|ch|第)\s*(\d+)', title_orig)
        if match:
            raw_num = int(match.group(1))
        else:
            match = re.search(r'\d+', title_orig)
            if match:
                raw_num = int(match.group(0))
                
        # Tracing values
        old_vol = current_vol
        old_ch = current_ch
        
        if auto_detect_volume and prev_raw_num > 0 and raw_num > 0 and raw_num < prev_raw_num and raw_num < 10:
            current_vol += 1
            current_ch = raw_num
            print(f"-> TRIGGERED Volume Reset! Vol {old_vol} -> {current_vol} at chapter orig='{title_orig}' (raw={raw_num}, prev_raw={prev_raw_num})")
            
        chapter_metrics[ch_id] = (current_vol, current_ch)
        print(f"Ch ID: {ch_id} | Orig: '{title_orig}' | Raw parsed num: {raw_num} | Assigned Vol-Ch: V{current_vol}-{current_ch}")
        
        current_ch += 1
        if raw_num > 0:
            prev_raw_num = raw_num
            
    conn.close()

if __name__ == "__main__":
    test_volume_mode_logic()
