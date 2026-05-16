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

# Daftar tugas translasi yang lagi jalan biar gak dobel
# chapter_id -> Task
active_tasks = {}
# chapter_id -> [asyncio.Queue] buat streaming ke frontend
translation_queues = {}

class BackgroundTranslator:
    @staticmethod
    async def run_chapter_translation(chapter_id: int, thread_id: int, target_lang: str, model: str | None = None, lm_url: str | None = None):
        """Mulai proses translasi bab di background."""
        if chapter_id in active_tasks:
            print(f"⚠️ Bab {chapter_id} lagi diterjemahin, gak usah dobel.")
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
        # 1. Siapkan data bab-nya
        content_original = None
        system_prompt = ""

        with SessionLocal() as db:
            stmt = select(Chapter).where(Chapter.id == chapter_id)
            chapter = db.execute(stmt).scalar_one_or_none()
            
            if not chapter:
                print(f"❌ Bab {chapter_id} gak ada di database.")
                return
                
            if not chapter.content_original:
                print(f"❌ Bab {chapter_id} kosong, gak ada yang bisa diterjemahin.")
                chapter.translation_status = "error"
                db.commit()
                return

            # Ambil konten aslinya dan set status ke processing
            content_original = chapter.content_original
            chapter.translation_status = "processing"
            db.commit()

            # 2. Rakit prompt-nya lewat ContextEngine
            system_prompt = ContextEngine.build_translation_prompt(db, thread_id, target_lang, content_original)

        # 3. Panggil AI-nya (LM Studio)
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
                
                # Kirim hasil streaming ke queue biar frontend bisa update real-time
                if chapter_id in translation_queues:
                    for q in translation_queues[chapter_id]:
                        await q.put(content)
                
                # Simpan berkala tiap 20 chunk biar kalau putus gak ilang semua
                if chunk_count % 20 == 0:
                    with SessionLocal() as db:
                        ch = db.get(Chapter, chapter_id)
                        if ch:
                            ch.content_translated = full_content
                            db.commit()

            # Selesai! Simpan hasil final dan update lorebook kalau ada istilah baru
            with SessionLocal() as db:
                ContextEngine.auto_save_glossary(db, thread_id, full_content)
                
                ch = db.get(Chapter, chapter_id)
                if ch:
                    ch.content_translated = full_content
                    ch.translation_status = "done"
                    db.commit()
                    print(f"✅ Bab {chapter_id} beres diterjemahin di background.")

            # Cek apakah harus otomatis nerjemahin bab selanjutnya (prefetch)
            await BackgroundTranslator.check_and_prefetch(chapter_id, thread_id, target_lang, model, lm_url)

        except Exception as e:
            print(f"❌ Error pas nerjemahin bab {chapter_id}: {e}")
            with SessionLocal() as db:
                ch = db.get(Chapter, chapter_id)
                if ch:
                    ch.translation_status = "error"
                    db.commit()
        finally:
            # Kasih sinyal ke queue kalau sudah beres
            if chapter_id in translation_queues:
                for q in translation_queues[chapter_id]:
                    await q.put("[DONE]")

    @staticmethod
    async def check_and_prefetch(current_chapter_id: int, thread_id: int, target_lang: str, model: str | None, lm_url: str | None):
        """Otomatis terjemahin bab berikutnya biar user gak nunggu lama."""
        try:
            with SessionLocal() as db:
                gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
                if not gs or not gs.prefetch_enabled:
                    return

                curr_ch = db.get(Chapter, current_chapter_id)
                if not curr_ch: return

                # Cari bab selanjutnya berdasarkan urutan (order)
                next_ch = db.execute(
                    select(Chapter)
                    .where(Chapter.thread_id == thread_id)
                    .where(Chapter.order == curr_ch.order + 1)
                ).scalar_one_or_none()

                if next_ch and next_ch.translation_status == "idle" and not next_ch.content_translated:
                    print(f"⏩ Prefetch bab selanjutnya: {next_ch.id}")
                    # Jalankan translasi bab berikutnya tanpa nunggu (non-blocking)
                    asyncio.create_task(
                        BackgroundTranslator.run_chapter_translation(
                            next_ch.id, thread_id, target_lang, model, lm_url
                        )
                    )
        except Exception as e:
            print(f"⚠️ Gagal prefetch: {e}")
