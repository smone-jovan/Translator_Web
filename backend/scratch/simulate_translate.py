import sys
sys.path.append('d:/code_xI/Translator_Web/backend')

import asyncio
import traceback

async def main():
    print("Simulating translation for chapter 685...", flush=True)
    try:
        from database import SessionLocal, Chapter
        db = SessionLocal()
        ch = db.get(Chapter, 685)
        if not ch:
            print("Chapter 685 not found!", flush=True)
            return
        thread_id = ch.thread_id
        print(f"Chapter 685 belongs to Thread {thread_id}", flush=True)
        
        # Reset its status so it doesn't get skipped or ignored
        ch.translation_status = "idle"
        ch.content_translated = None
        db.commit()
        print("Database status reset successfully to idle", flush=True)
        
        from services.background_translator import BackgroundTranslator
        print("Starting _do_translate...", flush=True)
        # Run translation directly
        await BackgroundTranslator._do_translate(
            chapter_id=685,
            thread_id=thread_id,
            target_lang="English",
            force_extract=True,
            force_overwrite=True
        )
        print("Finished _do_translate!", flush=True)
    except Exception as e:
        print("EXCEPTION OCCURRED IN SIMULATION:", flush=True)
        traceback.print_exc()

asyncio.run(main())
