import sqlite3
import os

db_path = 'backend/app.db'
if os.path.exists(db_path):
    print(f"Migrating {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # 1. Update chapters table
        new_chapters_cols = [
            ('title_original', 'TEXT'),
            ('title_translated', 'TEXT'),
            ('translation_status', 'TEXT DEFAULT "idle"')
        ]
        for col_name, col_type in new_chapters_cols:
            try:
                cursor.execute(f'ALTER TABLE chapters ADD COLUMN {col_name} {col_type}')
                print(f"[OK] Added column to chapters: {col_name}")
            except sqlite3.OperationalError:
                print(f"[SKIP] Column chapters.{col_name} already exists.")

        # 2. Update global_settings table
        new_settings_cols = [
            ('lm_url', 'TEXT DEFAULT "http://localhost:1234"'),
            ('lm_model', 'TEXT'),
            ('target_language', 'TEXT DEFAULT "Indonesian"')
        ]
        for col_name, col_type in new_settings_cols:
            try:
                cursor.execute(f'ALTER TABLE global_settings ADD COLUMN {col_name} {col_type}')
                print(f"[OK] Added column to global_settings: {col_name}")
            except sqlite3.OperationalError:
                print(f"[SKIP] Column global_settings.{col_name} already exists.")

        # 3. Migrate 'title' data to 'title_original'
        try:
            cursor.execute('UPDATE chapters SET title_original = title WHERE title_original IS NULL')
            print("[OK] Data migrated from 'title' to 'title_original'.")
        except sqlite3.OperationalError:
            pass

        # 4. Ensure at least one global setting exists
        cursor.execute('SELECT count(*) FROM global_settings')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO global_settings (lm_url, target_language) VALUES (?, ?)', ("http://localhost:1234", "Indonesian"))
            print("[OK] Initialized default global settings.")

        conn.commit()
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
    finally:
        conn.close()
else:
    print(f"Database {db_path} not found. Nothing to migrate.")
