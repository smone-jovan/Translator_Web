import asyncio
import json
import re
import time
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import SessionLocal, Chapter, GlobalSetting, Thread
from services.context_engine import ContextEngine
from services.ai.factory import AIProviderFactory
from services.ai.settings import resolve_active_base_url, resolve_active_model, get_chapter_translation_max_tokens
from services.ai.base import TRUNCATED_MARKER, PROHIBITED_MARKER
from services.fidelity_checker import verify_translation_fidelity
from services.prompt_templates import (
    MAX_CONTINUATIONS,
    CONTINUATION_TAIL_CHARS,
    LOOP_DETECTION_TAIL_CHARS,
    LOOP_DETECTION_WINDOW,
    LOOP_DETECTION_THRESHOLD,
    STREAM_SAVE_INTERVAL,
    build_continuation_prompt,
)
from routers.scrape import html_to_markdown
import httpx

# Registry for active chapter translations to prevent duplicates
# chapter_id -> Task
active_tasks = {}
# chapter_id -> [asyncio.Queue] for streaming
translation_queues = {}

# Strong references to prevent garbage collection of wrapper tasks
_prefetch_tasks = set()

# Global lock to ensure single-concurrency for AI requests under Soft Load
translation_lock = asyncio.Lock()
# Global state to track last request timestamp for pacing (ADR-029)
_last_api_call_time = 0.0

class ActiveBatch:
    def __init__(self, thread_id: int, chapter_ids: list, target_lang: str, model: str | None, lm_url: str | None, force_extract: bool, force_overwrite: bool, translation_mode: str = "quality", fetch_only: bool = False):
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
        self.fetch_only = fetch_only
        self.is_stopped = False
        self.extract_count = 0  # Track how many chapters have had glossary extraction
        self.quota_exhausted = False
        self.active_task = None
        self.is_waiting = True

active_batches = {} # thread_id -> ActiveBatch

# Master Queue for global sequential batch translation
master_batch_queue = asyncio.Queue()
master_worker_task = None

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
        "empty content", # gemini 3.1 flash lite safety glitch
        "empty translation",
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
    @classmethod
    async def run_chapter_translation(
        cls,
        chapter_id: int,
        thread_id: int,
        target_lang: str,
        model: str | None = None,
        lm_url: str | None = None,
        force_extract: bool = False,
        force_overwrite: bool = False,
        translation_mode: str = "quality"
    ) -> bool:
        try:
            return await cls._run_translation_internal(
                chapter_id, thread_id, target_lang, model, lm_url, force_extract, force_overwrite, translation_mode
            )
        finally:
            if chapter_id in translation_queues:
                for q in translation_queues[chapter_id]:
                    try:
                        q.put_nowait("[DONE]")
                    except Exception:
                        pass

    @classmethod
    async def _run_translation_internal(
        cls,
        chapter_id: int,
        thread_id: int,
        target_lang: str,
        model: str | None = None,
        lm_url: str | None = None,
        force_extract: bool = False,
        force_overwrite: bool = False,
        translation_mode: str = "quality"
    ) -> bool:
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
            return True
        except Exception as e:
            print(f"[ERROR] Single translation task failed: {e}")
            from database import SessionLocal, Chapter
            with SessionLocal() as db:
                ch = db.get(Chapter, chapter_id)
                if ch:
                    ch.translation_status = "error"
                    db.commit()
            
            if chapter_id in translation_queues:
                for q in translation_queues[chapter_id]:
                    try:
                        q.put_nowait(f"\n\n[SYSTEM ERROR] Translation failed: {e}")
                    except Exception:
                        pass
            return False
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
        translation_mode: str = "quality",
        fetch_only: bool = False
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
                if getattr(chapter, "source_url", None):
                    print(f"[SCRAPE] Chapter {chapter_id} has no content. Scraping on-demand from {chapter.source_url}")
                    try:
                        async with httpx.AsyncClient(
                            follow_redirects=True,
                            timeout=30.0,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; TranslatorBot/1.0)"},
                        ) as client:
                            resp = await client.get(chapter.source_url)
                            resp.raise_for_status()
                        
                        fetched_title, fetched_markdown = html_to_markdown(resp.text)
                        
                        is_vip = False
                        if chapter.source_url and "/vip/" in chapter.source_url.lower():
                            is_vip = True
                        elif fetched_title and "VIP章节" in fetched_title:
                            is_vip = True
                        elif not fetched_markdown or len(fetched_markdown) < 50:
                            is_vip = True

                        if is_vip:
                            print(f"[VIP] Chapter {chapter_id} flagged as VIP.")
                            chapter.translation_status = "vip"
                            chapter.content_original = "[VIP CHAPTER] Bab ini terkunci atau tidak dapat diakses (VIP)."
                            db.commit()
                            return False
                        
                        chapter.content_original = fetched_markdown
                        if not chapter.title_original and fetched_title:
                            chapter.title_original = fetched_title
                        db.commit()
                        print(f"[SCRAPE] Successfully scraped chapter {chapter_id}.")
                    except Exception as e:
                        print(f"[ERROR] Failed to scrape chapter {chapter_id}: {e}")
                        chapter.translation_status = "error"
                        db.commit()
                        return False
                else:
                    print(f"[ERROR] Chapter {chapter_id} has no original content and no source_url. Translation aborted.")
                    chapter.translation_status = "error"
                    db.commit()
                    return False

            if fetch_only:
                print(f"[FETCH_ONLY] Chapter {chapter_id} raw text successfully fetched. Skipping translation.")
                chapter.translation_status = "idle"  # Keep it idle so it can be translated later
                db.commit()
                return True

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
                    await BackgroundTranslator._enforce_pacing(model, gs)
                    await ContextEngine.extract_glossary_pass(db, thread_id, chapter.content_original, lm_url, model, target_lang)

                # Ambil konten aslinya dan set status ke processing
                content_original = chapter.content_original

                image_pattern = re.compile(r"(!\[.*?\]\(.*?\))")
                protected_images = image_pattern.findall(content_original)
                protected_content = content_original
                for i, img_md in enumerate(protected_images):
                    protected_content = protected_content.replace(img_md, f"\n❖IMAGE_{i}❖\n")

                chapter.translation_status = "processing"
                db.commit()

                # 2. Rakit prompt-nya lewat ContextEngine
                system_prompt = ContextEngine.build_translation_prompt(
                    db, thread_id, target_lang, content_original, translation_mode,
                    model=model
                )
                print(f"[DEBUG] Chapter {chapter_id} - System Prompt Length: {len(system_prompt)} chars, Original Content Length: {len(content_original)} chars")

            # Pace the API requests based on selected model's strict RPM limits (ADR-029)
            await BackgroundTranslator._enforce_pacing(model, gs)

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
                else:
                    max_tokens = None  # No cap when disabled
                full_content = ""
                sent_clean_content = ""
                chunk_count = 0
                notes_started = False
                notes_header_pattern = re.compile(
                    r"(\n\s*[-—*_#]*\s*Translato(?:r|ion)['s]*\s*Notes?[:\s]?|\n\s*[-—*_#]*\s*Glossary[:\s]?|\n\s*[-—*_#]*\s*New Terms[:\s]?)", 
                    re.IGNORECASE
                )
                continuation_round = 0
                while continuation_round <= MAX_CONTINUATIONS:
                    # Build messages: first round uses original prompt, continuation rounds use "continue" prompt
                    if continuation_round == 0:
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": protected_content},
                        ]
                    else:
                        print(f"[CONTINUE] Chapter {chapter_id} was truncated. Auto-continuing (round {continuation_round}/{MAX_CONTINUATIONS})...")
                        # Send the last CONTINUATION_TAIL_CHARS as context so the AI knows where it left off
                        tail = full_content[-CONTINUATION_TAIL_CHARS:] if len(full_content) > CONTINUATION_TAIL_CHARS else full_content
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": protected_content},
                            {"role": "assistant", "content": f"... {tail}"},
                            {"role": "user", "content": build_continuation_prompt()},
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
                        if chunk_count % STREAM_SAVE_INTERVAL == 0:
                            with SessionLocal() as db:
                                ch = db.get(Chapter, chapter_id)
                                if ch:
                                    clean_partial = ContextEngine.clean_final_translation(
                                        full_content,
                                        always_hide_thoughts=bool(always_hide_thoughts)
                                    )
                                    for i, img_md in enumerate(protected_images):
                                        clean_partial = re.sub(rf"❖(?:IMAGE|GAMBAR|Image|gambar)_{i}❖", img_md, clean_partial, flags=re.IGNORECASE)
                                    ch.content_translated = clean_partial
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

                    # ----- ANTI 40K TOKEN LEAK & WORD-SOUP PREVENTION -----
                    # 1. Prevent LLM from continuing an infinite substring repetition loop
                    tail = full_content[-LOOP_DETECTION_TAIL_CHARS:]
                    is_looping = False
                    for i in range(len(tail) - LOOP_DETECTION_WINDOW):
                        substr = tail[i:i+LOOP_DETECTION_WINDOW]
                        if tail.count(substr) > LOOP_DETECTION_THRESHOLD:
                            is_looping = True
                            break
                    
                    if is_looping:
                        print(f"[WARN] Chapter {chapter_id} truncated due to infinite loop hallucination! Aborting continuation to save tokens.")
                        break

                    # 2. Prevent runaway length explosion (>5x original length or >35k chars)
                    if len(full_content) > max(len(content_original) * 5, 25000):
                        print(f"[WARN] Chapter {chapter_id} translation length exceeded safe ratio ({len(full_content)} chars vs {len(content_original)} orig chars). Aborting continuation.")
                        break

                    # 3. Prevent unpunctuated word-soup dictionary dump continuation
                    if re.search(r"(?:[A-Za-z0-9-]{2,}\s+){20,}[A-Za-z0-9-]{2,}", tail):
                        print(f"[WARN] Chapter {chapter_id} detected word-soup vocabulary dump in stream tail! Aborting continuation.")
                        break
                    # --------------------------------------------------------

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

                        for i, img_md in enumerate(protected_images):
                            clean_to_save = re.sub(rf"❖(?:IMAGE|GAMBAR|Image|gambar)_{i}❖", img_md, clean_to_save, flags=re.IGNORECASE)
                            if img_md not in clean_to_save:
                                clean_to_save += f"\n\n{img_md}\n\n"

                        if not clean_to_save:
                            raise ValueError(
                                f"AI provider returned an empty translation for chapter {chapter_id}."
                            )

                        ContextEngine.auto_save_glossary(db, thread_id, full_content)

                        # Post-translation fidelity check (ADR-072)
                        fidelity = verify_translation_fidelity(
                            content_original, clean_to_save, chapter_id=chapter_id
                        )
                        if fidelity["is_suspicious"]:
                            print(f"[FIDELITY] Chapter {chapter_id}: Translation may be incomplete. "
                                  f"Original: {fidelity['original_paragraphs']} paragraphs, "
                                  f"Translated: {fidelity['translated_paragraphs']} paragraphs "
                                  f"(ratio: {fidelity['paragraph_ratio']})")
                            ch.fidelity_warning = (
                                f"Suspicious translation structure: Original has {fidelity['original_paragraphs']} paragraphs, "
                                f"Translated has {fidelity['translated_paragraphs']} paragraphs (ratio: {fidelity['paragraph_ratio']:.2f})."
                            )
                        else:
                            ch.fidelity_warning = None

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
                        task = asyncio.create_task(
                            BackgroundTranslator.run_chapter_translation(
                                next_ch.id, thread_id, target_lang, model, lm_url
                            )
                        )
                        _prefetch_tasks.add(task)
                        task.add_done_callback(_prefetch_tasks.discard)
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
        translation_mode: str = "quality",
        fetch_only: bool = False
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
            translation_mode=translation_mode,
            fetch_only=fetch_only
        )
        active_batches[thread_id] = batch
        
        # Masukkan ke antrian global
        await master_batch_queue.put(batch)
        
        # Jalankan master worker jika belum aktif
        global master_worker_task
        if master_worker_task is None or master_worker_task.done():
            master_worker_task = asyncio.create_task(BackgroundTranslator._master_loop())

    @staticmethod
    async def stop_batch(thread_id: int):
        """Hentikan batch translation yang sedang berjalan."""
        batch = active_batches.get(thread_id)
        if batch:
            batch.is_stopped = True
            batch.is_waiting = False
            if batch.active_task:
                batch.active_task.cancel()
            # Cancel current active chapter task if any
            if batch.current_chapter_id in active_tasks:
                active_tasks[batch.current_chapter_id].cancel()
            active_batches.pop(thread_id, None)

    @staticmethod
    async def stop_all_batches():
        """Hentikan SEMUA batch translation yang sedang berjalan (untuk workspace switch)."""
        for t_id in list(active_batches.keys()):
            await BackgroundTranslator.stop_batch(t_id)
            
        while not master_batch_queue.empty():
            try:
                master_batch_queue.get_nowait()
                master_batch_queue.task_done()
            except Exception:
                pass

    @staticmethod
    async def _master_loop():
        """Master worker that processes batches sequentially across all threads."""
        while True:
            batch = await master_batch_queue.get()
            if batch.is_stopped:
                master_batch_queue.task_done()
                continue
                
            batch.is_waiting = False
            
            # Buat task agar bisa di-cancel independen oleh stop_batch
            batch_task = asyncio.create_task(BackgroundTranslator._run_batch_worker(batch))
            batch.active_task = batch_task
            
            try:
                await batch_task
            except asyncio.CancelledError:
                print(f"[MASTER QUEUE] Master loop cancelled. Cancelling active batch for thread {batch.thread_id}.")
                batch_task.cancel()
                raise
            except Exception as e:
                print(f"[MASTER QUEUE] Batch worker for thread {batch.thread_id} crashed: {e}")
            finally:
                master_batch_queue.task_done()

    @staticmethod
    async def _enforce_pacing(model: str, gs: 'GlobalSetting' = None):
        """Enforces strict RPM limit pacing. Called before ANY LLM API call."""
        global _last_api_call_time
        llm_provider = "lm_studio"
        resolved_model = model
        num_keys = 1
        
        if gs:
            llm_provider = getattr(gs, "llm_provider", "lm_studio")
            from services.ai.settings import resolve_active_model
            resolved_model = resolve_active_model(gs, model)
            
            # Count keys to divide delay
            if llm_provider == "gemini" and getattr(gs, "gemini_api_keys", None):
                try:
                    import json
                    keys = json.loads(gs.gemini_api_keys)
                    if isinstance(keys, list) and len(keys) > 0:
                        num_keys = len(keys)
                except Exception:
                    pass
            elif llm_provider == "openai" and getattr(gs, "openai_api_keys", None):
                try:
                    import json
                    keys = json.loads(gs.openai_api_keys)
                    if isinstance(keys, list) and len(keys) > 0:
                        num_keys = len(keys)
                except Exception:
                    pass

        required_delay = 1.0
        if llm_provider == "gemini":
            m_lower = (resolved_model or "").lower()
            if "gemini-3.1-flash-lite" in m_lower or "gemini-3.5-flash-lite" in m_lower:
                required_delay = 4.2  # 15 RPM = 4.0s (Safety margin: 4.2s)
            elif "gemma-4-31b" in m_lower or "gemma-4-26b" in m_lower:
                required_delay = 2.2  # 30 RPM = 2.0s (Safety margin: 2.2s)
            elif "gemini-2.5-flash-lite" in m_lower:
                required_delay = 6.2  # 10 RPM = 6.0s (Safety margin: 6.2s)
            else:
                required_delay = 12.2  # 5 RPM models (gemini-3.6-flash, gemini-3.5-flash, gemini-3-flash, gemini-2.5-flash, etc.)
                
        # Divide delay by number of active API keys to multiply RPM
        required_delay = required_delay / num_keys
        
        # Hard cap minimum delay to avoid aggressive banning (e.g. 1.6s minimum for multiple keys)
        if num_keys > 1:
            required_delay = max(required_delay, 1.6)

        global _pacing_lock
        try:
            _pacing_lock
        except NameError:
            import asyncio
            _pacing_lock = asyncio.Lock()

        import asyncio
        async with _pacing_lock:
            time_since_last = time.time() - _last_api_call_time
            if time_since_last < required_delay:
                wait_time = required_delay - time_since_last
                print(f"[PACING] [RPM Safety Guard] Delaying request for {wait_time:.2f}s to respect {resolved_model} RPM limits ({num_keys} keys active)...")
                await asyncio.sleep(wait_time)

            _last_api_call_time = time.time()
            
            # Round-robin rotate the key on EVERY request so we distribute load evenly across keys
            if gs and num_keys > 1:
                from services.ai.secrets import rotate_api_key
                rotate_api_key(llm_provider, gs)

    @staticmethod
    def _calculate_concurrency_limit(provider: str, api_keys_json: str | None = None) -> int:
        if provider == "lm_studio":
            return 1
            
        num_keys = 1
        if provider == "gemini" and api_keys_json:
            try:
                import json
                keys = json.loads(api_keys_json)
                if isinstance(keys, list) and len(keys) > 0:
                    num_keys = len(keys)
            except Exception:
                pass
                
        return min(max(num_keys * 3, 2), 20)

    @staticmethod
    async def _run_batch_worker(batch: ActiveBatch):
        """Worker loop yang mengeksekusi bab secara CONCURRENT (Ngebut Paralel)."""
        try:
            from services.ai.secrets import QuotaExhaustedError
            import asyncio
            
            provider = "lm_studio"
            api_keys_json = None
            
            with SessionLocal() as db:
                gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
                if gs:
                    provider = gs.llm_provider or "lm_studio"
                    if provider == "gemini":
                        api_keys_json = getattr(gs, "gemini_api_keys", None)
                    elif provider == "openai":
                        api_keys_json = getattr(gs, "openai_api_keys", None)
            
            concurrency_limit = BackgroundTranslator._calculate_concurrency_limit(provider, api_keys_json)
            
            print(f"[BATCH] Starting batch worker with {concurrency_limit} concurrent tasks for thread {batch.thread_id}.")
            
            queue = asyncio.Queue()
            for ch_id in list(batch.chapter_ids):
                queue.put_nowait(ch_id)
                
            pending_retries: dict[int, int] = {}
            
            async def worker(worker_id: int):
                while batch.chapter_ids and not batch.is_stopped:
                    try:
                        ch_id = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        await asyncio.sleep(1.0)
                        continue
                        
                    batch.current_chapter_id = ch_id
                    
                    with SessionLocal() as db:
                        chapter = db.get(Chapter, ch_id)
                        if chapter:
                            batch.current_chapter_title = f"Ch {chapter.order}: {chapter.title_original or 'Untitled'}"
                        else:
                            batch.current_chapter_title = f"Chapter {ch_id}"
                            
                    try:
                        # Only run glossary extraction on the first N chapters (extract_chapter_count)
                        # After that, disable to prevent 300+ term accumulation
                        should_extract = False
                        if batch.force_extract:
                            with SessionLocal() as db:
                                gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
                                extract_limit = gs.extract_chapter_count if gs else 12
                            if batch.extract_count < extract_limit:
                                should_extract = True
                                batch.extract_count += 1
                                if batch.extract_count >= extract_limit:
                                    print(f"[EXTRACT] Reached extraction limit ({extract_limit} chapters). Disabling glossary scan for remaining chapters.")

                        success = await BackgroundTranslator._do_translate(
                            chapter_id=ch_id, thread_id=batch.thread_id,
                            target_lang=batch.target_lang, model=batch.model,
                            lm_url=batch.lm_url, force_extract=should_extract,
                            force_overwrite=batch.force_overwrite,
                            translation_mode=batch.translation_mode, fetch_only=batch.fetch_only
                        )
                        
                        if batch.fetch_only and success:
                            import random
                            await asyncio.sleep(random.uniform(1.0, 2.5))
                            
                        if success:
                            pending_retries.pop(ch_id, None)
                            if ch_id in batch.chapter_ids:
                                batch.chapter_ids.remove(ch_id)
                            batch.completed += 1
                        else:
                            pending_retries.pop(ch_id, None)
                            if ch_id in batch.chapter_ids:
                                batch.chapter_ids.remove(ch_id)
                            batch.failed_ids.append(ch_id)
                            batch.completed += 1
                            
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        if isinstance(e, QuotaExhaustedError):
                            fallback_sequence = ['gemini-3.1-flash-lite', 'gemini-3.5-flash-lite', 'gemma-4-31b', 'gemma-4-26b', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
                            with SessionLocal() as db:
                                gs_fresh = db.execute(select(GlobalSetting)).scalar_one_or_none()
                                current_model = gs_fresh.gemini_model if (gs_fresh and gs_fresh.gemini_model) else ""
                                if gs_fresh and gs_fresh.llm_provider == "gemini" and current_model in fallback_sequence:
                                    idx = fallback_sequence.index(current_model)
                                    if idx + 1 < len(fallback_sequence):
                                        next_model = fallback_sequence[idx + 1]
                                        print(f"[AUTO-FALLBACK] Gemini model '{current_model}' exhausted on all keys. Switching to '{next_model}'.")
                                        gs_fresh.gemini_model = next_model
                                        batch.model = next_model
                                        db.commit()
                                        pending_retries[ch_id] = 0
                                        queue.put_nowait(ch_id)
                                        continue
                            
                            print(f"[FATAL] Batch translation stopped: {e}")
                            batch.is_stopped = True
                            batch.quota_exhausted = True
                            break
                            
                        if _is_retryable_error(e) and pending_retries.get(ch_id, 0) < 15: # Increase max retries internally to handle many keys
                            err_str = str(e).lower()
                            is_quota_limit = "429" in err_str and any(q in err_str for q in ["quota", "exhausted"])
                            
                            if is_quota_limit:
                                retry_count = pending_retries.get(ch_id, 0) # Don't increment for quota
                            else:
                                retry_count = pending_retries.get(ch_id, 0) + 1
                                
                            pending_retries[ch_id] = retry_count
                            delay = RETRY_BASE_DELAY * (2 ** (retry_count - 1)) if retry_count > 0 else RETRY_BASE_DELAY
                            print(f"[RETRY] Chapter {ch_id} hit service error (attempt {retry_count}/15). Re-queuing after {delay:.0f}s. Error: {e}")
                            is_quota_limit = "429" in err_str and any(q in err_str for q in ["quota", "exhausted"])
                            
                            from services.ai.secrets import rotate_api_key, mark_key_exhausted, get_active_api_key, QuotaExhaustedError
                            with SessionLocal() as db:
                                gs_fresh = db.execute(select(GlobalSetting)).scalar_one_or_none()
                                if gs_fresh and gs_fresh.llm_provider:
                                    try:
                                        if is_quota_limit:
                                            current_key = get_active_api_key(gs_fresh.llm_provider, gs_fresh)
                                            if current_key:
                                                mark_key_exhausted(gs_fresh.llm_provider, current_key, gs_fresh.gemini_model)
                                        rotate_api_key(gs_fresh.llm_provider, gs_fresh)
                                    except QuotaExhaustedError as qe:
                                        pass
                                    
                                ch = db.get(Chapter, ch_id)
                                if ch:
                                    ch.translation_status = "idle"
                                db.commit()
                            
                            async def delayed_requeue(cid, d):
                                await asyncio.sleep(d)
                                if getattr(batch, "is_stopped", False) == False:
                                    queue.put_nowait(cid)
                            
                            asyncio.create_task(delayed_requeue(ch_id, delay))
                        else:
                            pending_retries.pop(ch_id, None)
                            print(f"[ERROR] Batch chapter {ch_id} failed permanently: {e}")
                            batch.failed_ids.append(ch_id)
                            batch.completed += 1
                            if ch_id in batch.chapter_ids:
                                batch.chapter_ids.remove(ch_id)
                    finally:
                        await asyncio.sleep(1.0)
                        
            tasks = [asyncio.create_task(worker(i)) for i in range(concurrency_limit)]
            await asyncio.gather(*tasks, return_exceptions=True)

        except asyncio.CancelledError:
            print(f"[STOP] Batch translation worker for thread {batch.thread_id} dibatalkan.")
        finally:
            active_batches.pop(batch.thread_id, None)
