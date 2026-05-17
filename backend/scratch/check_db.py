import sys
sys.path.append('d:/code_xI/Translator_Web/backend')
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database import SessionLocal, GlobalSetting, Chapter, Thread
from sqlalchemy import select

db = SessionLocal()
print("=== GLOBAL SETTINGS ===")
gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
if gs:
    print(f"id: {gs.id}")
    print(f"lm_url: {gs.lm_url}")
    print(f"lm_model: {gs.lm_model}")
    print(f"target_language: {gs.target_language}")
    print(f"prefetch_enabled: {gs.prefetch_enabled}")
    print(f"prefetch_count: {gs.prefetch_count}")
    print(f"prefetch_mode: {gs.prefetch_mode}")
else:
    print("No global settings found!")

print("\n=== RECENT CHAPTERS & STATUS ===")
stmt = select(Chapter).order_by(Chapter.id.desc()).limit(15)
chapters = db.execute(stmt).scalars().all()
for ch in chapters:
    title_safe = ch.title_original or 'Untitled'
    print(f"ID: {ch.id} | Order: {ch.order} | Title: {title_safe} | Status: {ch.translation_status} | Translated (len): {len(ch.content_translated or '')}")
