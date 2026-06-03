import sys
sys.path.insert(0, '.')
from database import SessionLocal, Chapter

with SessionLocal() as db:
    for ch_id in [2036, 2037]:
        ch = db.get(Chapter, ch_id)
        if ch:
            ct = ch.content_translated or ''
            print(f"Ch {ch_id}: status={ch.translation_status}, len={len(ct)}")
            if ct:
                print(f"  Preview: {ct[:200]}...")
        else:
            print(f"Ch {ch_id}: NOT FOUND")