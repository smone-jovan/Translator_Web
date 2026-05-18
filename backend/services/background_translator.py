import asyncio
import json
import re
import time
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import SessionLocal, Chapter, GlobalSetting
from services.context_engine import ContextEngine
from services.ai.factory import AIProviderFactory
from services.ai.settings import resolve_active_base_url, resolve_active_model, get_chapter_translation_max_tokens

# Registry for active chapter translations to prevent duplicates
# chapter_id -> Task
active_tasks = {}
# chapter_id -> [asyncio.Queue] for streaming
translation_queues = {}

# Global lock to ensure single-concurrency for AI requests under Soft Load
translation_lock = asyncio.Lock()
# Global state to track last request timestamp for pacing (ADR-029)
_last_api_call_time = 0.0

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
        """Start background chapter translation task."""
        if chapter_id in active_tasks:
            print(f"[WARN] Chapter {chapter_id} is already being translated. Ignoring duplicate request.")
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
    ) -> bool:
        # 1. Siapkan data bab-nya
        content_original = None
        system_prompt = ""
        use_lock = False

        with SessionLocal() as db:
            stmt = select(Chapter).where(Chapter.id == chapter_id)
            chapter = db.execute(stmt).scalar_one_or_none()
            
            if not chapter:
                print(f"[ERROR] Chapter {chapter_id} not found in database.")
                return False
                
            if not chapter.content_original:
                print(f"[ERROR] Chapter {chapter_id} has no original content. Translation aborted.")
                chapter.translation_status = "error"
                db.commit()
                return False

            if chapter.content_translated and not force_overwrite:
                print(f"[SKIP] Chapter {chapter_id} already has a translation. Skipping.")
                return True

            # Resolve lm_url and model from GlobalSetting if not explicitly passed
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            if gs:
                if not lm_url:
                    lm_url = resolve_active_base_url(gs)
                if not model:
                    model = resolve_active_model(gs)
            
            if not lm_url:
                lm_url = "http://localhost:1234"

            # Check prefetch_mode to see if we should enforce sequential 1-concurrency
            prefetch_mode = getattr(gs, "prefetch_mode", "soft") if gs else "soft"
            use_lock = (prefetch_mode == "soft")

        # Acquire lock if needed BEFORE we update state and start LLM operations
        if use_lock:
            print(f"[LOCK] [Soft Load] Chapter {chapter_id} waiting for AI translation lock...")
            await translation_lock.acquire()
            print(f"[LOCK] [Soft Load] Chapter {chapter_id} acquired AI translation lock.")

        try:
            with SessionLocal() as db:
                stmt = select(Chapter).where(Chapter.id == chapter_id)
                chapter = db.execute(stmt).scalar_one_or_none()
                if not chapter:
                    return False

                # AI Extract First Logic
                if force_extract:
                    print(f"[EXTRACT] Starting glossary extraction for chapter {chapter_id} before translation...")
                    await ContextEngine.extract_glossary_pass(db, thread_id, chapter.content_original, lm_url, model)

                # Ambil konten aslinya dan set status ke processing
                content_original = chapter.content_original
                chapter.translation_status = "processing"
                db.commit()

                # 2. Rakit prompt-nya lewat ContextEngine
                system_prompt = ContextEngine.build_translation_prompt(db, thread_id, target_lang, content_original)

            # Pace the API requests based on selected model's strict RPM limits (ADR-029)
            global _last_api_call_time
            llm_provider = "lm_studio"
            resolved_model = model
            if gs:
                llm_provider = getattr(gs, "llm_provider", "lm_studio")
                resolved_model = resolve_active_model(gs, model)

            required_delay = 1.0
            if llm_provider == "gemini":
                m_lower = (resolved_model or "").lower()
                if "gemini-3.1-flash-lite" in m_lower:
                    required_delay = 4.2  # 15 RPM = 4.0s (Safety margin: 4.2s)
                elif "gemini-2.5-flash-lite" in m_lower:
                    required_delay = 6.2  # 10 RPM = 6.0s (Safety margin: 6.2s)
                elif "gemini-2.5-flash" in m_lower:
                    required_delay = 12.2  # 5 RPM = 12.0s (Safety margin: 12.2s)
                elif "gemini-3-flash" in m_lower:
                    required_delay = 12.2  # 5 RPM = 12.0s (Safety margin: 12.2s)
                elif "gemma-4-31b" in m_lower:
                    required_delay = 4.2  # 15 RPM = 4.0s (Safety margin: 4.2s)
                else:
                    required_delay = 12.2

            time_since_last = time.time() - _last_api_call_time
            if time_since_last < required_delay:
                wait_time = required_delay - time_since_last
                print(f"[PACING] [RPM Safety Guard] Delaying request for {wait_time:.2f}s to respect {resolved_model} RPM limits...")
                await asyncio.sleep(wait_time)

            _last_api_call_time = time.time()

            # 3. Panggil AI-nya (LM Studio)
            try:
                provider = AIProviderFactory.get_provider(base_url=lm_url or "http://localhost:1234", model=model)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_original},
                ]

                always_hide_thoughts = getattr(gs, "always_hide_thoughts", 1) if gs else 1
                max_tokens = get_chapter_translation_max_tokens(gs)
                full_content = ""
                sent_clean_content = ""
                chunk_count = 0
                notes_started = False
                notes_header_pattern = re.compile(
                    r"(\n\s*[-—*_]*\s*Translator['s]*\s*Notes?|\n\s*[-—*_]*\s*###\s*Translator['s]*\s*Notes?|\n\s*[-—*_]*\s*Notes?[:\s])", 
                    re.IGNORECASE
                )
                
                async for content in provider.stream_chat(messages=messages, temperature=0.3, max_tokens=max_tokens):
                    full_content += content
                    chunk_count += 1
                    
                    # Kirim hasil streaming ke queue biar frontend bisa update real-time
                    if chapter_id in translation_queues:
                        clean_content = full_content
                        if always_hide_thoughts:
                            clean_content = ContextEngine.strip_thinking_blocks(clean_content)
                            
                        if not notes_started:
                            match = notes_header_pattern.search(clean_content)
                            if match:
                                notes_started = True
                                cutoff = match.start()
                                clean_before_notes = clean_content[:cutoff]
                                new_chunk = clean_before_notes[len(sent_clean_content):]
                                if new_chunk:
                                    for q in translation_queues[chapter_id]:
                                        await q.put(new_chunk)
                                    sent_clean_content = clean_before_notes
                            else:
                                new_chunk = clean_content[len(sent_clean_content):]
                                if new_chunk:
                                    for q in translation_queues[chapter_id]:
                                        await q.put(new_chunk)
                                    sent_clean_content = clean_content
                    
                    # Simpan berkala tiap 20 chunk biar kalau putus gak ilang semua
                    if chunk_count % 20 == 0:
                        with SessionLocal() as db:
                            ch = db.get(Chapter, chapter_id)
                            if ch:
                                clean_to_save = full_content
                                if always_hide_thoughts:
                                    clean_to_save = ContextEngine.strip_thinking_blocks(clean_to_save)
                                ch.content_translated = ContextEngine.strip_translator_notes(clean_to_save)
                                db.commit()

                if not full_content.strip():
                    print(f"[WARN] Empty stream for chapter {chapter_id}; retrying with non-streaming completion.")
                    full_content = await provider.chat_completion(messages=messages, temperature=0.3, max_tokens=max_tokens)

                # Selesai! Simpan hasil final dan update lorebook kalau ada istilah baru
                with SessionLocal() as db:
                    ch = db.get(Chapter, chapter_id)
                    if ch:
                        clean_to_save = full_content
                        if always_hide_thoughts:
                            clean_to_save = ContextEngine.strip_thinking_blocks(clean_to_save)
                        clean_to_save = ContextEngine.strip_translator_notes(clean_to_save).strip()

                        if not clean_to_save:
                            raise ValueError(
                                f"AI provider returned an empty translation for chapter {chapter_id}."
                            )

                        ContextEngine.auto_save_glossary(db, thread_id, full_content)
                        ch.content_translated = clean_to_save
                        ch.translation_status = "done"
                        db.commit()
                        print(f"[OK] Chapter {chapter_id} background translation completed successfully.")

                # Cek apakah harus otomatis nerjemahin bab selanjutnya (prefetch)
                # Dihapus dari sini karena prefetch hanya dipicu saat pengguna mengakses bab, mencegah infinite runaway translation.
                return True

            except Exception as e:
                print(f"[ERROR] Failed to translate chapter {chapter_id}: {e}")
                with SessionLocal() as db:
                    ch = db.get(Chapter, chapter_id)
                    if ch:
                        ch.translation_status = "error"
                        db.commit()
                return False
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
        """Otomatis terjemahin bab berikutnya dalam batas prefetch_count dari posisi baca saat ini."""
        try:
            with SessionLocal() as db:
                gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
                if not gs or not gs.prefetch_enabled:
                    return

                curr_ch = db.get(Chapter, current_chapter_id)
                if not curr_ch: return

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

                for next_ch in next_chapters:
                    if next_ch.translation_status == "idle" and not next_ch.content_translated:
                        print(f"[PREFETCH] [{prefetch_mode.capitalize()} Load] Queueing prefetch for chapter: {next_ch.id} (Order: {next_ch.order})")
                        asyncio.create_task(
                            BackgroundTranslator.run_chapter_translation(
                                next_ch.id, thread_id, target_lang, model, lm_url
                            )
                        )
        except Exception as e:
            print(f"[WARN] Prefetch failed: {e}")

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
                    success = await BackgroundTranslator._do_translate(
                        chapter_id=ch_id,
                        thread_id=batch.thread_id,
                        target_lang=batch.target_lang,
                        model=batch.model,
                        lm_url=batch.lm_url,
                        force_extract=batch.force_extract,
                        force_overwrite=batch.force_overwrite
                    )
                    if not success:
                        batch.failed_ids.append(ch_id)
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
