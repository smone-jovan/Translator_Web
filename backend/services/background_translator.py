import asyncio
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import SessionLocal, Chapter, GlobalSetting
from services.context_engine import ContextEngine
from services.ai_provider import AIProvider

# Registry for active chapter translations to prevent duplicates
# chapter_id -> Task
active_tasks = {}
# chapter_id -> [asyncio.Queue] for streaming
translation_queues = {}

class BackgroundTranslator:
    @staticmethod
    async def run_chapter_translation(chapter_id: int, thread_id: int, target_lang: str, model: str | None = None, lm_url: str | None = None):
        """Orchestrate the translation of a single chapter."""
        if chapter_id in active_tasks:
            print(f"⚠️ Translation already in progress for chapter {chapter_id}")
            return

        task = asyncio.create_task(BackgroundTranslator._do_translate(chapter_id, thread_id, target_lang, model, lm_url))
        active_tasks[chapter_id] = task
        try:
            await task
        finally:
            if chapter_id in active_tasks:
                del active_tasks[chapter_id]

    @staticmethod
    async def _do_translate(chapter_id: int, thread_id: int, target_lang: str, model: str | None = None, lm_url: str | None = None):
        # 1. Prepare Chapter
        content_original = None
        system_prompt = ""

        with SessionLocal() as db:
            stmt = select(Chapter).where(Chapter.id == chapter_id)
            chapter = db.execute(stmt).scalar_one_or_none()
            
            if not chapter:
                print(f"❌ Chapter {chapter_id} not found in DB.")
                return
                
            if not chapter.content_original:
                print(f"❌ Chapter {chapter_id} has no original content.")
                chapter.translation_status = "error"
                db.commit()
                return

            # Capture content BEFORE commit to avoid expiration issues
            content_original = chapter.content_original
            chapter.translation_status = "processing"
            db.commit()

            # 2. Build Prompt
            system_prompt = ContextEngine.build_translation_prompt(db, thread_id, target_lang, content_original)

        # 3. Setup AI
        try:
            ai = AIProvider(lm_url or "http://localhost:1234")
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_original},
                ],
                "temperature": 0.3,
                "max_tokens": 8192,
                "stream": True,
            }
            if model:
                payload["model"] = model

            full_content = ""
            chunk_count = 0
            
            async for content in ai.stream_chat(payload):
                full_content += content
                chunk_count += 1
                
                # Push to streaming queues
                if chapter_id in translation_queues:
                    for q in translation_queues[chapter_id]:
                        await q.put(content)
                
                # Periodically save
                if chunk_count % 20 == 0:
                    with SessionLocal() as db:
                        ch = db.get(Chapter, chapter_id)
                        if ch:
                            ch.content_translated = full_content
                            db.commit()

            # Finalize
            with SessionLocal() as db:
                # Auto-save glossary from translated content
                ContextEngine.auto_save_glossary(db, thread_id, full_content)
                
                ch = db.get(Chapter, chapter_id)
                if ch:
                    ch.content_translated = full_content
                    ch.translation_status = "done"
                    db.commit()
                    print(f"✅ Background translation DONE for chapter {chapter_id}")

            # --- PREFETCH TRIGGER ---
            await BackgroundTranslator.check_and_prefetch(chapter_id, thread_id, target_lang, model, lm_url)

        except Exception as e:
            print(f"❌ Background translation ERROR for chapter {chapter_id}: {e}")
            with SessionLocal() as db:
                ch = db.get(Chapter, chapter_id)
                if ch:
                    ch.translation_status = "error"
                    db.commit()
        finally:
            # Signal end to queues
            if chapter_id in translation_queues:
                for q in translation_queues[chapter_id]:
                    await q.put("[DONE]")

    @staticmethod
    async def check_and_prefetch(current_chapter_id: int, thread_id: int, target_lang: str, model: str | None, lm_url: str | None):
        """Checks if prefetch is enabled and triggers translation for the next chapter."""
        try:
            with SessionLocal() as db:
                gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
                if not gs or not gs.prefetch_enabled:
                    return

                curr_ch = db.get(Chapter, current_chapter_id)
                if not curr_ch: return

                # Find next chapter
                next_ch = db.execute(
                    select(Chapter)
                    .where(Chapter.thread_id == thread_id)
                    .where(Chapter.order == curr_ch.order + 1)
                ).scalar_one_or_none()

                if next_ch and next_ch.translation_status == "idle" and not next_ch.content_translated:
                    print(f"⏩ Prefetching NEXT chapter: {next_ch.id} (Order {next_ch.order})")
                    # Trigger next translation (non-blocking)
                    asyncio.create_task(
                        BackgroundTranslator.run_chapter_translation(
                            next_ch.id, thread_id, target_lang, model, lm_url
                        )
                    )
        except Exception as e:
            print(f"⚠️ Prefetch Error: {e}")
