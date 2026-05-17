import sqlite3
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('app.db')
cursor = conn.cursor()

print("=== STARTING LOREBOOK DATABASE CLEANUP ===")

# Retrieve all entries
rows = cursor.execute("SELECT id, thread_id, original_term, translated_term, notes FROM lorebook_entries").fetchall()

deleted_count = 0
updated_count = 0

# Compile Chinese character check regex
# Matches Hanzi characters (common + extended)
chinese_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

for row_id, thread_id, original_term, translated_term, notes in rows:
    # 1. Check if original_term has at least one Chinese character
    if not chinese_pattern.search(original_term):
        print(f"Deleting garbage entry ID {row_id} (No Chinese characters): '{original_term}' -> '{translated_term}'")
        cursor.execute("DELETE FROM lorebook_entries WHERE id = ?", (row_id,))
        deleted_count += 1
        continue
        
    # 2. Check if original_term is extremely long (like a whole sentence)
    if len(original_term) > 40:
        print(f"Deleting too long entry ID {row_id} (Length {len(original_term)}): '{original_term[:20]}...' -> '{translated_term[:20]}...'")
        cursor.execute("DELETE FROM lorebook_entries WHERE id = ?", (row_id,))
        deleted_count += 1
        continue

    # 3. Clean up formatting stars or punctuation from valid terms
    cleaned_orig = original_term.strip(" \t\n\r*•-“”\"'")
    cleaned_orig = re.sub(r"\*\*$", "", cleaned_orig)
    cleaned_orig = cleaned_orig.strip()

    cleaned_trans = translated_term.strip(" \t\n\r*•-“”\"'")
    cleaned_trans = re.sub(r"\*\*$", "", cleaned_trans)
    cleaned_trans = cleaned_trans.strip()

    if cleaned_orig != original_term or cleaned_trans != translated_term:
        print(f"Cleaning formatting for ID {row_id}: '{original_term}' -> '{cleaned_orig}' | '{translated_term}' -> '{cleaned_trans}'")
        cursor.execute(
            "UPDATE lorebook_entries SET original_term = ?, translated_term = ? WHERE id = ?",
            (cleaned_orig, cleaned_trans, row_id)
        )
        updated_count += 1

# 4. Inject 弥安 -> Millian mapping for consistent translations
# Let's see what threads exist
threads = cursor.execute("SELECT id FROM threads").fetchall()
for (t_id,) in threads:
    # Check if 弥安 is already in glossary for this thread
    exists = cursor.execute(
        "SELECT id FROM lorebook_entries WHERE thread_id = ? AND original_term = ?",
        (t_id, "弥安")
    ).fetchone()
    
    if not exists:
        print(f"Adding unified term 弥安 -> Millian for Thread ID {t_id}")
        cursor.execute(
            "INSERT INTO lorebook_entries (thread_id, original_term, translated_term, notes, usage_count, is_locked, is_archived) VALUES (?, ?, ?, ?, 0, 0, 0)",
            (t_id, "弥安", "Millian", "The same character as 米莲 (Millian), sometimes written by author as 弥安 due to typo or alternative romanization.",)
        )
        updated_count += 1

conn.commit()

print(f"\n=== CLEANUP COMPLETED: Deleted {deleted_count} entries, Updated/Added {updated_count} entries. ===")

# Show remaining active terms to confirm
print("\n=== CURRENT ACTIVE LOREBOOK ENTRIES ===")
active_rows = cursor.execute("SELECT id, original_term, translated_term, notes FROM lorebook_entries WHERE is_archived = 0").fetchall()
for r in active_rows:
    print(f"ID: {r[0]} | '{r[1]}' -> '{r[2]}' | Notes: {r[3]}")

conn.close()
