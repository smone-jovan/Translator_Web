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
from services.ai.base import TRUNCATED_MARKER, PROHIBITED_MARKER

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
    def __init__(self, thread_id: int, chapter_ids: list, target_lang: str, model: str | None, lm_url: str | None, force_extract: bool, force_overwrite: bool, translation_mode: str = "quality"):
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
        self.translation_mode = translation_mode
        self.is_stopped = False
        self.active_task = None

active_batches = {} # thread_id -> ActiveBatch

# Retry configuration for service unavailable errors
MAX_RETRIES = 3
RETRY_BASE_DELAY = 10.0  # seconds, exponential backoff: 10s, 20s, 40s


def _is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable (rate limit, service unavailable, connection issues)."""
    err_str = str(error).lower()
    retryable_patterns = [
        "429",           # rate limit
        "503",           # service unavailable
        "502",           # bad gateway
        "408",           # request timeout
        "high load",
        "overloaded",
        "rate limit",
        "too many requests",
        "service unavailable",
        "connection refused",
        "connection reset",
        "timeout",
        "temporarily",
        "try again",
        "empty content",       # Added to handle Gemini blank responses
        "empty translation",   # Added to handle over-truncation
    ]
    return any(pattern in err_str for pattern in retryable_patterns)

class BackgroundTranslator:
    @staticmethod
    async def run_chapter_translation(
        chapter_id: int, 
        thread_id: int, 
        target_lang: str, 
        model: str | None = None, 
        lm_url: str | None = None,
        force_extract: bool = False,
        force_overwrite: bool = False,
        translation_mode: str = "quality"
    ):
        """Start background chapter translation task."""
        if chapter_id in active_tasks:
            print(f"[WARN] Chapter {chapter_id} is already being translated. Ignoring duplicate request.")
            return

        task = asyncio.create_task(
            BackgroundTranslator._do_translate(
                chapter_id, thread_id, target_lang, model, lm_url, force_extract, force_overwrite, translation_mode
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
        force_overwrite: bool = False,
        translation_mode: str = "quality"
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

            if chapter.translation_status == "done" and chapter.content_translated and not force_overwrite:
                print(f"[SKIP] Chapter {chapter_id} already has a translation. Skipping.")
                return True

            # Skip table of contents / metadata pages (AI hallucinates when translating these)
            content_preview = (chapter.content_original or "").strip()
            toc_indicators = ["简介", "目录", "第一章", "第二章", "第三章", "第四章", "第五章",
                              "第六章", "第七章", "第八章", "第九章", "第十章"]
            toc_count = sum(1 for indicator in toc_indicators if indicator in content_preview)
            # If content has many chapter titles listed (TOC pattern), skip
            is_toc_page = len(content_preview) < 5000 and toc_count >= 5
            if is_toc_page:
                print(f"[SKIP] Chapter {chapter_id} appears to be a table of contents ({toc_count} chapter refs found). Skipping.")
                chapter.translation_status = "done"
                chapter.content_translated = chapter.content_original
                db.commit()
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
                    await ContextEngine.extract_glossary_pass(db, thread_id, chapter.content_original, lm_url, model, target_lang)

                # Ambil konten aslinya dan set status ke processing
                content_original = chapter.content_original
                chapter.translation_status = "processing"
                db.commit()

                # 2. Rakit prompt-nya lewat ContextEngine
                system_prompt = ContextEngine.build_translation_prompt(
                    db, thread_id, target_lang, content_original, translation_mode
                )

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

                always_hide_thoughts = getattr(gs, "always_hide_thoughts", 1) if gs else 1
                max_tokens = get_chapter_translation_max_tokens(gs)
                # Mode-aware token cap:
                # - Safety cap ENABLED: always respect the cap (both modes)
                # - Safety cap DISABLED: Quality=uncapped, Fast=10K max
                cap_enabled = getattr(gs, "chapter_token_cap_enabled", 1) if gs else 1
                if cap_enabled:
                    # Cap is on — respect it regardless of mode
                    pass  # max_tokens already set by get_chapter_translation_max_tokens
                elif translation_mode == "quality":
                    max_tokens = None  # No cap for quality when disabled
                else:
                    max_tokens = 10000  # Fast always caps at 10K
                full_content = ""
                sent_clean_content = ""
                chunk_count = 0
                notes_started = False
                notes_header_pattern = re.compile(
                    r"(\n\s*[-—*_#]*\s*Translato(?:r|ion)['s]*\s*Notes?[:\s]?|\n\s*[-—*_#]*\s*Glossary[:\s]?|\n\s*[-—*_#]*\s*New Terms[:\s]?)", 
                    re.IGNORECASE
                )

                MAX_CONTINUATIONS = 3
                continuation_round = 0

                while continuation_round <= MAX_CONTINUATIONS:
                    # Build messages: first round uses original prompt, continuation rounds use "continue" prompt
                    if continuation_round == 0:
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": content_original},
                        ]
                    else:
                        print(f"[CONTINUE] Chapter {chapter_id} was truncated. Auto-continuing (round {continuation_round}/{MAX_CONTINUATIONS})...")
                        # Send the last 500 chars as context so the AI knows where it left off
                        tail = full_content[-500:] if len(full_content) > 500 else full_content
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": content_original},
                            {"role": "assistant", "content": f"... {tail}"},
                            {"role": "user", "content": "Your previous translation was cut off mid-sentence. Continue translating from exactly where you stopped. Do NOT repeat any already-translated text. Just continue the translation naturally."},
                        ]

                    round_truncated = False
                    round_prohibited = False
                    async for content in provider.stream_chat(messages=messages, temperature=0.3, max_tokens=max_tokens):
                        # Check for truncation marker
                        if content == TRUNCATED_MARKER:
                            round_truncated = True
                            continue

                        # Check for prohibited/filtered marker
                        if content == PROHIBITED_MARKER:
                            round_prohibited = True
                            continue

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
                                    ch.content_translated = ContextEngine.clean_final_translation(
                                        full_content,
                                        always_hide_thoughts=bool(always_hide_thoughts)
                                    )
                                    db.commit()

                    # Handle prohibited/filtered response — skip this chapter entirely
                    if round_prohibited:
                        print(f"[PROHIBITED] Chapter {chapter_id} was blocked by AI content filter. Skipping.")
                        if chapter_id in translation_queues:
                            for q in translation_queues[chapter_id]:
                                await q.put("[PROHIBITED]")
                        with SessionLocal() as db:
                            ch = db.get(Chapter, chapter_id)
                            if ch:
                                ch.translation_status = "prohibited"
                                ch.content_translated = None
                                db.commit()
                        return False

                    if not round_truncated:
                        break  # Translation complete, no truncation

                    continuation_round += 1
                    if continuation_round > MAX_CONTINUATIONS:
                        print(f"[WARN] Chapter {chapter_id} still truncated after {MAX_CONTINUATIONS} continuation rounds. Saving partial result.")

                if not full_content.strip():
                    print(f"[WARN] Empty stream for chapter {chapter_id}; retrying with non-streaming completion.")
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content_original},
                    ]
                    full_content = await provider.chat_completion(messages=messages, temperature=0.3, max_tokens=max_tokens)

                # Selesai! Simpan hasil final dan update lorebook kalau ada istilah baru
                with SessionLocal() as db:
                    ch = db.get(Chapter, chapter_id)
                    if ch:
                        clean_to_save = ContextEngine.clean_final_translation(
                            full_content,
                            always_hide_thoughts=bool(always_hide_thoughts)
                        )

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
                # For retryable errors (429/503/etc), re-raise so batch worker can retry
                if _is_retryable_error(e):
                    raise
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
        force_overwrite: bool = False,
        translation_mode: str = "quality"
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
            force_overwrite=force_overwrite,
            translation_mode=translation_mode
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
        """Worker loop yang mengeksekusi bab secara berurutan, dengan retry untuk error service unavailable."""
        try:
            pending_retries: dict[int, int] = {}  # chapter_id -> retry_count

            while True:
                # Build work queue: original chapters + pending retries
                work_queue: list[int] = []
                for ch_id in list(batch.chapter_ids):
                    if ch_id not in pending_retries or pending_retries[ch_id] < MAX_RETRIES:
                        work_queue.append(ch_id)
                # Add retry chapters that aren't in the original list anymore
                for ch_id in list(pending_retries.keys()):
                    if ch_id not in work_queue and pending_retries[ch_id] < MAX_RETRIES:
                        work_queue.append(ch_id)

                if not work_queue or batch.is_stopped:
                    break

                ch_id = work_queue.pop(0)
                batch.current_chapter_id = ch_id

                # Update status bab ke memori untuk info ke frontend
                with SessionLocal() as db:
                    chapter = db.get(Chapter, ch_id)
                    if chapter:
                        batch.current_chapter_title = f"Ch {chapter.order}: {chapter.title_original or 'Untitled'}"
                    else:
                        batch.current_chapter_title = f"Chapter {ch_id}"

                try:
                    success = await BackgroundTranslator._do_translate(
                        chapter_id=ch_id,
                        thread_id=batch.thread_id,
                        target_lang=batch.target_lang,
                        model=batch.model,
                        lm_url=batch.lm_url,
                        force_extract=batch.force_extract,
                        force_overwrite=batch.force_overwrite,
                        translation_mode=batch.translation_mode
                    )
                    if success:
                        # Chapter done — remove from tracking so it won't be re-processed
                        pending_retries.pop(ch_id, None)
                        if ch_id in batch.chapter_ids:
                            batch.chapter_ids.remove(ch_id)
                        batch.completed += 1
                    else:
                        # Failed but not retryable (e.g., prohibited, no content)
                        pending_retries.pop(ch_id, None)
                        if ch_id in batch.chapter_ids:
                            batch.chapter_ids.remove(ch_id)
                        batch.failed_ids.append(ch_id)
                        batch.completed += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if _is_retryable_error(e) and pending_retries.get(ch_id, 0) < MAX_RETRIES:
                        retry_count = pending_retries.get(ch_id, 0) + 1
                        pending_retries[ch_id] = retry_count
                        delay = RETRY_BASE_DELAY * (2 ** (retry_count - 1))
                        print(f"[RETRY] Chapter {ch_id} hit service error (attempt {retry_count}/{MAX_RETRIES}). "
                              f"Re-queuing after {delay:.0f}s delay. Error: {e}")
                        
                        # Rotate API key if applicable, then reset chapter status
                        from services.ai.secrets import rotate_api_key
                        with SessionLocal() as db:
                            gs_fresh = db.execute(select(GlobalSetting)).scalar_one_or_none()
                            if gs_fresh and gs_fresh.llm_provider:
                                # Rotate the key globally
                                rotate_api_key(gs_fresh.llm_provider, gs_fresh)
                            
                            ch = db.get(Chapter, ch_id)
                            if ch:
                                ch.translation_status = "idle"
                            db.commit()
                        await asyncio.sleep(delay)
                        continue  # Don't increment completed — will retry
                    else:
                        # Not retryable or max retries exceeded
                        pending_retries.pop(ch_id, None)
                        print(f"[ERROR] Batch chapter {ch_id} failed permanently: {e}")
                        batch.failed_ids.append(ch_id)
                        batch.completed += 1

                # Istirahat 1 detik antar bab biar GPU gak overheat
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            print(f"[STOP] Batch translation worker for thread {batch.thread_id} dibatalkan.")
        finally:
            active_batches.pop(batch.thread_id, None)
