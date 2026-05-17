import sqlite3
import sys

conn = sqlite3.connect('app.db')
sys.stdout.reconfigure(encoding='utf-8')

print("=== Miyan / Millian Related Terms in lorebook_entries ===")
cursor = conn.cursor()
rows = cursor.execute("""
    SELECT id, original_term, translated_term, notes 
    FROM lorebook_entries 
    WHERE original_term LIKE '%米%' 
       OR original_term LIKE '%弥%' 
       OR translated_term LIKE '%Mil%' 
       OR translated_term LIKE '%Miy%'
""").fetchall()

for row in rows:
    print(f"ID: {row[0]} | Original: {row[1]} | Translated: {row[2]} | Notes: {row[3]}")

print("\n=== All Lorebook Entries containing English sentences ===")
rows_eng = cursor.execute("""
    SELECT id, original_term, translated_term 
    FROM lorebook_entries
    WHERE LENGTH(original_term) > 30 
       OR original_term LIKE '%the%' 
       OR original_term LIKE '%Winnie%'
""").fetchall()

for row in rows_eng:
    print(f"ID: {row[0]} | Original: {row[1][:60]}... | Translated: {row[2][:60]}...")

conn.close()
