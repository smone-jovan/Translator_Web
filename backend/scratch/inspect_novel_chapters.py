import sqlite3
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

db_path = os.path.join(os.path.dirname(__file__), "..", "app.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find thread
cursor.execute("SELECT id, title FROM threads")
threads = cursor.fetchall()
print("=== THREADS IN DB ===")
target_thread_id = None
for t in threads:
    print(f"ID: {t[0]} | Title: {t[1]}")
    if "Engagement" in str(t[1]) or "Save Me" in str(t[1]):
        target_thread_id = t[0]

if not target_thread_id:
    print("\nCould not find target thread by title, using thread_id = 4 as default")
    target_thread_id = 4
else:
    print(f"\nFound target thread! ID: {target_thread_id}")

print(f"\n=== CHAPTERS OF THREAD {target_thread_id} AROUND TRANSITION ===")
# Query chapters around 90-110 in order
cursor.execute(
    "SELECT id, `order`, title_original, title_translated FROM chapters WHERE thread_id = ? ORDER BY `order` ASC",
    (target_thread_id,)
)
chapters = cursor.fetchall()

# Print around index 90 to 115
for idx, c in enumerate(chapters):
    if 90 <= idx <= 120:
        print(f"Index: {idx} | ID: {c[0]} | Order: {c[1]} | Orig: {repr(c[2])} | Trans: {repr(c[3])}")

conn.close()
