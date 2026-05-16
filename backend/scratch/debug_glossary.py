import sqlite3
import json

db_path = r"d:\code_xI\Translator_Web\backend\app.db"

def check():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- LOREBOOK ENTRIES ---")
    cursor.execute("SELECT id, thread_id, original_term, notes FROM lorebook_entries ORDER BY id DESC LIMIT 10")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- RECENT CHAPTER TRANSLATION ---")
    cursor.execute("SELECT id, content_translated FROM chapters WHERE content_translated IS NOT NULL ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Chapter ID: {row[0]}")
        print("Content (Last 500 chars):")
        print(row[1][-500:] if row[1] else "None")
    
    conn.close()

if __name__ == "__main__":
    check()
