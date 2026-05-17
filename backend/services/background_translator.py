import asyncio
import json
import re
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

# Global lock to ensure single-concurrency for AI requests under Soft Load
translation_lock = asyncio.Lock()

class ActiveBatch:
    def __init__(self, thread_id: int, chapter_ids: list, target_lang: str, model: str | None, lm_url: str | None, force_extract: bool, force_overwrite: bool):
        self.thread_id = thread_id
        self.chapter_ids = list(chapter_ids)
        self.total = len(chapter_ids)
        self.completed = 0
        self.failed_ids = []
        self.current_chapter_id = None
        self.current_chapter_title = ""
        self.target_lang = target_lang
        self.model = model
        self.lm_url = lm_url
        self.force_extract = force_extract
        self.force_overwrite = force_overwrite
        self.is_stopped = False
        self.active_task = None

active_batches = {} # thread_id -> ActiveBatch

class BackgroundTranslator:
    @staticmethod
    async def run_chapter_translation(
        chapter_id: int, 
        thread_id: int, 
        target_lang: str, 
        model: str | None = None, 
        lm_url: str | None = None,
        force_extract: bool = False,
        force_overwrite: bool = False
    ):
        """Mulai proses translasi bab di background."""
        if chapter_id in active_tasks:
            print(f"[PERINGATAN] Bab {chapter_id} sedang dalam proses penerjemahan aktif. Permintaan baru diabaikan.")
            return

        task = asyncio.create_task(
            BackgroundTranslator._do_translate(
                chapter_id, thread_id, target_lang, model, lm_url, force_extract, force_overwrite
            )
        )
        active_tasks[chapter_id] = task
        try:
            await task
        finally:
            if chapter_id in active_tasks:
                del active_tasks[chapter_id]

    @staticmethod
    async def _do_translate(
        chapter_id: int, 
        thread_id: int, 
        target_lang: str, 
        model: str | None = None, 
        lm_url: str | None = None,
        force_extract: bool = False,
        force_overwrite: bool = False
    ):
        # 1. Siapkan data bab-nya
        content_original = None
        system_prompt = ""
        use_lock = False

        with SessionLocal() as db:
            stmt = select(Chapter).where(Chapter.id == chapter_id)
            chapter = db.execute(stmt).scalar_one_or_none()
            
            if not chapter:
                print(f"[GALAT] Bab {chapter_id} tidak ditemukan di dalam basis data.")
                return
                
            if not chapter.content_original:
                print(f"[GALAT] Teks asli bab {chapter_id} kosong. Proses penerjemahan dibatalkan.")
                chapter.translation_status = "error"
                db.commit()
                return

            if chapter.content_translated and not force_overwrite:
                print(f"[LEWATI] Bab {chapter_id} sudah memiliki terjemahan. Melewati proses ini.")
                return

            # Resolve lm_url and model from GlobalSetting if not explicitly passed
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            if gs:
                if not lm_url:
                    lm_url = gs.lm_url
                if not model:
                    model = gs.lm_model
            
            if not lm_url:
                lm_url = "http://localhost:1234"

            # Check prefetch_mode to see if we should enforce sequential 1-concurrency
            prefetch_mode = getattr(gs, "prefetch_mode", "soft") if gs else "soft"
            use_lock = (prefetch_mode == "soft")

        # Acquire lock if needed BEFORE we update state and start LLM operations
        if use_lock:
            print(f"[KUNCI] [Muat Halus] Bab {chapter_id} sedang menunggu kunci terjemahan AI...")
            await translation_lock.acquire()
            print(f"[KUNCI] [Muat Halus] Bab {chapter_id} berhasil mendapatkan kunci terjemahan AI.")

        try:
            with SessionLocal() as db:
                stmt = select(Chapter).where(Chapter.id == chapter_id)
                chapter = db.execute(stmt).scalar_one_or_none()
                if not chapter:
                    return

                # AI Extract First Logic
                if force_extract:
                    print(f"[EKSTRAKSI AI] Memulai ekstraksi istilah penting untuk bab {chapter_id} sebelum menerjemahkan...")
                    await ContextEngine.extract_glossary_pass(db, thread_id, chapter.content_original, lm_url, model)

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
                notes_started = False
                notes_header_pattern = re.compile(
                    r"(\n\s*Translator['s]*\s*Notes?|\n\s*### Translator['s]*\s*Notes?|\n\s*Notes?[:\s])", 
                    re.IGNORECASE
                )
                
                async for content in ai.stream_chat(payload):
                    full_content += content
                    chunk_count += 1
                    
                    # Kirim hasil streaming ke queue biar frontend bisa update real-time
                    if chapter_id in translation_queues:
                        if not notes_started:
                            match = notes_header_pattern.search(full_content)
                            if match:
                                notes_started = True
                                cutoff = match.start()
                                sent_so_far = len(full_content) - len(content)
                                if cutoff > sent_so_far:
                                    chunk_to_send = full_content[sent_so_far:cutoff]
                                    for q in translation_queues[chapter_id]:
                                        await q.put(chunk_to_send)
                            else:
                                for q in translation_queues[chapter_id]:
                                    await q.put(content)
                    
                    # Simpan berkala tiap 20 chunk biar kalau putus gak ilang semua
                    if chunk_count % 20 == 0:
                        with SessionLocal() as db:
                            ch = db.get(Chapter, chapter_id)
                            if ch:
                                ch.content_translated = ContextEngine.strip_translator_notes(full_content)
                                db.commit()

                # Selesai! Simpan hasil final dan update lorebook kalau ada istilah baru
                with SessionLocal() as db:
                    ContextEngine.auto_save_glossary(db, thread_id, full_content)
                    
                    ch = db.get(Chapter, chapter_id)
                    if ch:
                        ch.content_translated = ContextEngine.strip_translator_notes(full_content)
                        ch.translation_status = "done"
                        db.commit()
                        print(f"[BERHASIL] Penerjemahan bab {chapter_id} selesai dilakukan di latar belakang.")

                # Cek apakah harus otomatis nerjemahin bab selanjutnya (prefetch)
                await BackgroundTranslator.check_and_prefetch(chapter_id, thread_id, target_lang, model, lm_url)

            except Exception as e:
                print(f"[GALAT] Terjadi kesalahan saat menerjemahkan bab {chapter_id}: {e}")
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
        finally:
            if use_lock:
                try:
                    translation_lock.release()
                    print(f"[BUKA KUNCI] [Muat Halus] Kunci terjemahan AI untuk bab {chapter_id} telah dilepaskan.")
                except RuntimeError:
                    pass

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

                # Cari bab-bab selanjutnya berdasarkan urutan (order)
                prefetch_count = getattr(gs, "prefetch_count", 1)
                prefetch_mode = getattr(gs, "prefetch_mode", "soft")
                
                next_chapters_stmt = (
                    select(Chapter)
                    .where(Chapter.thread_id == thread_id)
                    .where(Chapter.order > curr_ch.order)
                    .where(Chapter.order <= curr_ch.order + prefetch_count)
                    .order_by(Chapter.order)
                )
                next_chapters = db.execute(next_chapters_stmt).scalars().all()

                if prefetch_mode == "soft":
                    # Soft Load: Only prefetch the VERY NEXT chapter if it's idle
                    # This creates a sequential chain of translations
                    if next_chapters:
                        target_ch = next_chapters[0]
                        if target_ch.translation_status == "idle" and not target_ch.content_translated:
                            print(f"[PRA-TERJEMAH] [Muat Halus] Memulai pra-terjemahan untuk bab berikutnya: {target_ch.id}")
                            asyncio.create_task(
                                BackgroundTranslator.run_chapter_translation(
                                    target_ch.id, thread_id, target_lang, model, lm_url
                                )
                            )
                else:
                    # Hard Load: Prefetch ALL chapters in the range immediately in parallel
                    for next_ch in next_chapters:
                        if next_ch.translation_status == "idle" and not next_ch.content_translated:
                            print(f"[PRA-TERJEMAH] [Muat Cepat] Memulai pra-terjemahan simultan untuk bab: {next_ch.id} (Urutan: {next_ch.order})")
                            asyncio.create_task(
                                BackgroundTranslator.run_chapter_translation(
                                    next_ch.id, thread_id, target_lang, model, lm_url
                                )
                            )
        except Exception as e:
            print(f"[PERINGATAN] Gagal menjalankan pra-terjemahan: {e}")

    @staticmethod
    async def start_batch(
        thread_id: int,
        chapter_ids: list[int],
        target_lang: str,
        model: str | None = None,
        lm_url: str | None = None,
        force_extract: bool = False,
        force_overwrite: bool = False
    ):
        """Mulai proses batch translation secara berurutan (Sequential Queue)."""
        if thread_id in active_batches:
            await BackgroundTranslator.stop_batch(thread_id)

        batch = ActiveBatch(
            thread_id=thread_id,
            chapter_ids=chapter_ids,
            target_lang=target_lang,
            model=model,
            lm_url=lm_url,
            force_extract=force_extract,
            force_overwrite=force_overwrite
        )
        active_batches[thread_id] = batch
        
        # Mulai worker task di background
        worker_task = asyncio.create_task(BackgroundTranslator._run_batch_worker(batch))
        batch.active_task = worker_task

    @staticmethod
    async def stop_batch(thread_id: int):
        """Hentikan batch translation yang sedang berjalan."""
        batch = active_batches.get(thread_id)
        if batch:
            batch.is_stopped = True
            if batch.active_task:
                batch.active_task.cancel()
            # Cancel current active chapter task if any
            if batch.current_chapter_id in active_tasks:
                active_tasks[batch.current_chapter_id].cancel()
            active_batches.pop(thread_id, None)

    @staticmethod
    async def _run_batch_worker(batch: ActiveBatch):
        """Worker loop yang mengeksekusi bab secara berurutan."""
        try:
            for ch_id in list(batch.chapter_ids):
                if batch.is_stopped:
                    break
                
                batch.current_chapter_id = ch_id
                
                # Update status bab ke memori untuk info ke frontend
                with SessionLocal() as db:
                    chapter = db.get(Chapter, ch_id)
                    if chapter:
                        batch.current_chapter_title = f"Ch {chapter.order}: {chapter.title_original or 'Untitled'}"
                    else:
                        batch.current_chapter_title = f"Chapter {ch_id}"
                
                try:
                    # Jalankan translasi bab secara berurutan
                    await BackgroundTranslator._do_translate(
                        chapter_id=ch_id,
                        thread_id=batch.thread_id,
                        target_lang=batch.target_lang,
                        model=batch.model,
                        lm_url=batch.lm_url,
                        force_extract=batch.force_extract,
                        force_overwrite=batch.force_overwrite
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"[ERROR] Batch chapter {ch_id} failed: {e}")
                    batch.failed_ids.append(ch_id)
                finally:
                    # Selalu tambahkan ke hitungan completed baik sukses maupun gagal
                    batch.completed += 1
                
                # Istirahat 1 detik antar bab biar GPU gak overheat
                await asyncio.sleep(1.0)
                
        except asyncio.CancelledError:
            print(f"[STOP] Batch translation worker for thread {batch.thread_id} dibatalkan.")
        finally:
            active_batches.pop(batch.thread_id, None)
