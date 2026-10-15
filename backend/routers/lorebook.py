"""
Lorebook CRUD endpoints with bidirectional limit enforcement, locked pinning,
archive visibility/restoration, live capacity telemetry, and bulk operations.
"""

from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database import get_db, LorebookEntry, Thread, GlobalSetting
from services.context_engine import ContextEngine

router = APIRouter(prefix="/api", tags=["Lorebook"])


def _resolve_gender(gender_val: str | None, orig: str, trans: str, notes: str | None) -> str | None:
    if gender_val is not None and str(gender_val).strip() in ("", "NONE", "null", "None"):
        return None
    val = gender_val
    if not val and notes:
        import re
        match = re.search(r"\b(MALE|FEMALE)\b\s*[—–\-]", notes, re.IGNORECASE)
        if match:
            val = match.group(1).upper()
    if val and str(val).upper() in ("MALE", "FEMALE"):
        if ContextEngine.is_non_human_term(orig, trans, notes):
            return None
        return str(val).upper()
    return None


class LorebookCreate(BaseModel):
    original_term: str
    translated_term: str
    notes: str | None = None
    gender: str | None = None
    is_locked: bool | None = False
    is_archived: bool | None = False


class LorebookBulkCreate(BaseModel):
    entries: list[LorebookCreate]
    is_locked: bool | None = None


class LorebookOut(BaseModel):
    id: int
    thread_id: int
    original_term: str
    translated_term: str
    notes: str | None = None
    gender: str | None = None
    is_locked: bool = False
    is_archived: bool = False
    auto_extracted: bool = False
    usage_count: int = 0
    last_used_at: datetime | str | None = None
    created_at: datetime | str | None = None

    model_config = ConfigDict(from_attributes=True)


class LockToggle(BaseModel):
    is_locked: bool


class ArchiveToggle(BaseModel):
    is_archived: bool


class PresetApplyRequest(BaseModel):
    target_language: str | None = None
    lock_entries: bool = True


class LorebookBulkRequest(BaseModel):
    action: Literal["lock", "unlock", "archive", "restore", "delete", "clean_garbage", "import"]
    entry_ids: list[int] | None = None
    entries: list[LorebookCreate] | None = None


def enforce_context_limit(thread_id: int, db: Session, protected_ids: set[int] | None = None):
    """
    Bidirectionally enforce global max_context_terms limit on glossary entries of a thread:
    1. If active entries exceed limit: archive surplus unlocked entries (ordered by
       usage_count ASC, last_used_at/created_at ASC, id ASC) WITHOUT deleting notes
       (since archived entries are already excluded from prompt injection).
    2. If active entries are below limit and archived entries exist: automatically
       restore (unarchive) top-priority archived entries (ordered by is_locked DESC,
       usage_count DESC, last_used_at/created_at DESC, id DESC) up to the limit.
    """
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    limit = gs.max_context_terms if (gs and gs.max_context_terms) else 150

    active_stmt = (
        select(LorebookEntry)
        .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)
        .order_by(LorebookEntry.id)
    )
    active_entries = list(db.execute(active_stmt).scalars().all())

    protected = protected_ids or set()

    if len(active_entries) > limit:
        surplus_count = len(active_entries) - limit
        evictable = [e for e in active_entries if not e.is_locked and e.id not in protected]

        def evict_sort_key(e):
            timestamp = e.last_used_at or e.created_at
            timestamp_val = timestamp.timestamp() if hasattr(timestamp, "timestamp") else 0
            return (e.usage_count or 0, timestamp_val, e.id or 0)

        evictable.sort(key=evict_sort_key)
        for entry in evictable[:surplus_count]:
            entry.is_archived = True
        db.commit()
        return

    if len(active_entries) < limit:
        archived_stmt = (
            select(LorebookEntry)
            .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == True)
        )
        archived_entries = list(db.execute(archived_stmt).scalars().all())
        if not archived_entries:
            return

        available_slots = limit - len(active_entries)

        def restore_sort_key(e):
            timestamp = e.last_used_at or e.created_at
            timestamp_val = timestamp.timestamp() if hasattr(timestamp, "timestamp") else 0
            return (1 if e.is_locked else 0, e.usage_count or 0, timestamp_val, e.id or 0)

        archived_entries.sort(key=restore_sort_key, reverse=True)
        for entry in archived_entries[:available_slots]:
            entry.is_archived = False
        db.commit()


@router.get("/threads/{thread_id}/lorebook", response_model=list[LorebookOut])
def list_lorebook(
    thread_id: int,
    include_archived: bool = Query(False, description="Include archived entries in response"),
    db: Session = Depends(get_db),
):
    """List lorebook entries for thread (active only by default; all if include_archived=True)."""
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    stmt = select(LorebookEntry).where(LorebookEntry.thread_id == thread_id)
    if not include_archived:
        stmt = stmt.where(LorebookEntry.is_archived == False)
    stmt = stmt.order_by(LorebookEntry.id)
    return db.execute(stmt).scalars().all()


@router.get("/threads/{thread_id}/lorebook/stats")
def get_lorebook_stats(thread_id: int, db: Session = Depends(get_db)):
    """Return glossary capacity and settings synchronization telemetry for the thread."""
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    max_limit = gs.max_context_terms if (gs and gs.max_context_terms) else 150
    translation_mode = (gs.translation_mode if (gs and gs.translation_mode) else "quality").lower()
    target_language = gs.target_language if (gs and gs.target_language) else "Indonesian"
    effective_prompt_limit = min(max_limit, 10) if translation_mode == "fast" else max_limit

    all_entries = db.execute(
        select(LorebookEntry).where(LorebookEntry.thread_id == thread_id)
    ).scalars().all()

    active_count = sum(1 for e in all_entries if not e.is_archived)
    archived_count = sum(1 for e in all_entries if e.is_archived)
    locked_count = sum(1 for e in all_entries if e.is_locked and not e.is_archived)
    male_count = sum(1 for e in all_entries if e.gender == "MALE")
    female_count = sum(1 for e in all_entries if e.gender == "FEMALE")
    neutral_count = sum(1 for e in all_entries if e.gender not in ("MALE", "FEMALE"))
    auto_extracted_count = sum(1 for e in all_entries if getattr(e, "auto_extracted", False))

    return {
        "thread_id": thread_id,
        "active_count": active_count,
        "locked_count": locked_count,
        "archived_count": archived_count,
        "total_count": len(all_entries),
        "male_count": male_count,
        "female_count": female_count,
        "neutral_count": neutral_count,
        "auto_extracted_count": auto_extracted_count,
        "max_context_terms": max_limit,
        "translation_mode": translation_mode,
        "effective_prompt_limit": effective_prompt_limit,
        "target_language": target_language,
    }


def _upsert_single_lorebook_entry(
    db: Session,
    thread_id: int,
    body: LorebookCreate,
) -> LorebookEntry:
    orig_clean = body.original_term.strip()
    trans_clean = body.translated_term.strip()
    now_utc = datetime.now()

    existing_stmt = select(LorebookEntry).where(
        LorebookEntry.thread_id == thread_id,
        func.lower(func.trim(LorebookEntry.original_term)) == orig_clean.lower()
    )
    existing_entry = db.execute(existing_stmt).scalars().first()
    if existing_entry:
        existing_entry.is_archived = False if body.is_archived is None else body.is_archived
        existing_entry.translated_term = trans_clean
        if body.notes is not None:
            existing_entry.notes = body.notes
        if body.gender is not None:
            existing_entry.gender = _resolve_gender(body.gender, existing_entry.original_term, trans_clean, existing_entry.notes)
        elif not existing_entry.gender and existing_entry.notes:
            existing_entry.gender = _resolve_gender(None, existing_entry.original_term, trans_clean, existing_entry.notes)
        if body.is_locked is not None:
            existing_entry.is_locked = body.is_locked
        existing_entry.usage_count = max(1, (existing_entry.usage_count or 0))
        existing_entry.last_used_at = now_utc
        return existing_entry

    entry = LorebookEntry(
        thread_id=thread_id,
        original_term=orig_clean,
        translated_term=trans_clean,
        notes=body.notes,
        gender=_resolve_gender(body.gender, orig_clean, trans_clean, body.notes),
        is_locked=body.is_locked if body.is_locked is not None else False,
        is_archived=body.is_archived if body.is_archived is not None else False,
        usage_count=1,
        last_used_at=now_utc,
    )
    db.add(entry)
    return entry


@router.post("/threads/{thread_id}/lorebook", response_model=LorebookOut)
def create_lorebook_entry(
    thread_id: int,
    body: LorebookCreate,
    db: Session = Depends(get_db),
):
    """Add term to lorebook, or restore/update if it was archived/exists."""
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    entry = _upsert_single_lorebook_entry(db, thread_id, body)
    db.commit()
    db.refresh(entry)

    if not entry.is_archived:
        enforce_context_limit(thread_id, db, protected_ids={entry.id})
        db.refresh(entry)
    return entry


@router.post("/threads/{thread_id}/lorebook/bulk", response_model=list[LorebookOut])
def create_lorebook_entries_bulk(
    thread_id: int,
    body: LorebookBulkCreate,
    db: Session = Depends(get_db),
):
    """Bulk create or import lorebook entries."""
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    saved_entries: list[LorebookEntry] = []
    for item in body.entries:
        if not item.original_term.strip() or not item.translated_term.strip():
            continue
        if body.is_locked is not None:
            item.is_locked = body.is_locked
        entry = _upsert_single_lorebook_entry(db, thread_id, item)
        saved_entries.append(entry)

    if saved_entries:
        db.commit()
        for e in saved_entries:
            db.refresh(e)
        enforce_context_limit(thread_id, db, protected_ids={e.id for e in saved_entries})
        for e in saved_entries:
            db.refresh(e)

    return saved_entries


@router.delete("/lorebook/{entry_id}")
def delete_lorebook_entry(entry_id: int, db: Session = Depends(get_db)):
    """Delete lorebook entry and restore any archived entry if capacity frees up."""
    stmt = select(LorebookEntry).where(LorebookEntry.id == entry_id)
    entry = db.execute(stmt).scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entry not found")

    t_id = entry.thread_id
    db.delete(entry)
    db.commit()
    enforce_context_limit(t_id, db)
    return {"deleted": True, "id": entry_id}


@router.put("/lorebook/{entry_id}", response_model=LorebookOut)
def update_lorebook_entry(
    entry_id: int,
    body: LorebookCreate,
    db: Session = Depends(get_db),
):
    """Update an existing lorebook entry and re-enforce active context limit."""
    stmt = select(LorebookEntry).where(LorebookEntry.id == entry_id)
    entry = db.execute(stmt).scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entry not found")

    if body.original_term != entry.original_term:
        conflict_stmt = select(LorebookEntry).where(
            LorebookEntry.thread_id == entry.thread_id,
            LorebookEntry.id != entry_id,
            LorebookEntry.original_term == body.original_term
        )
        conflict = db.execute(conflict_stmt).scalar_one_or_none()
        if conflict:
            raise HTTPException(409, f"An entry with original_term '{body.original_term}' already exists in this thread.")

    entry.original_term = body.original_term
    entry.translated_term = body.translated_term
    entry.notes = body.notes
    entry.gender = _resolve_gender(body.gender, entry.original_term, entry.translated_term, entry.notes)
    if body.is_locked is not None:
        entry.is_locked = body.is_locked
    if body.is_archived is not None:
        entry.is_archived = body.is_archived

    db.commit()
    db.refresh(entry)

    if not entry.is_archived:
        enforce_context_limit(entry.thread_id, db)
        db.refresh(entry)
    return entry


@router.post("/lorebook/{entry_id}/lock", response_model=LorebookOut)
def toggle_lorebook_lock(
    entry_id: int,
    body: LockToggle,
    db: Session = Depends(get_db),
):
    """Pin/lock a glossary entry to protect it from auto-archiving."""
    stmt = select(LorebookEntry).where(LorebookEntry.id == entry_id)
    entry = db.execute(stmt).scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entry not found")

    entry.is_locked = body.is_locked
    if body.is_locked and entry.is_archived:
        entry.is_archived = False
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/lorebook/{entry_id}/archive", response_model=LorebookOut)
def toggle_lorebook_archive(
    entry_id: int,
    body: ArchiveToggle,
    db: Session = Depends(get_db),
):
    """Manually archive or restore a glossary entry."""
    stmt = select(LorebookEntry).where(LorebookEntry.id == entry_id)
    entry = db.execute(stmt).scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entry not found")

    entry.is_archived = body.is_archived
    if body.is_archived:
        entry.is_locked = False
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/threads/{thread_id}/lorebook/bulk-action")
@router.post("/threads/{thread_id}/lorebook/action")
def bulk_lorebook_action(
    thread_id: int,
    body: LorebookBulkRequest,
    db: Session = Depends(get_db),
):
    """Execute bulk operations (lock, unlock, archive, restore, delete, clean_garbage, import) on a thread's lorebook."""
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    affected = 0

    if body.action == "clean_garbage":
        entries = db.execute(
            select(LorebookEntry).where(LorebookEntry.thread_id == thread_id)
        ).scalars().all()
        for e in entries:
            if not e.is_locked and ContextEngine.is_garbage_term(e.original_term, e.translated_term):
                db.delete(e)
                affected += 1
        if affected > 0:
            db.commit()
            enforce_context_limit(thread_id, db)
        return {"status": "ok", "action": body.action, "affected": affected}

    if body.action == "import":
        items = body.entries or []
        for item in items:
            orig = (item.original_term or "").strip()
            trans = (item.translated_term or "").strip()
            if not orig or not trans:
                continue
            existing = db.execute(
                select(LorebookEntry).where(
                    LorebookEntry.thread_id == thread_id,
                    func.lower(LorebookEntry.original_term) == orig.lower()
                )
            ).scalars().first()
            if existing:
                existing.translated_term = trans
                if item.notes is not None:
                    existing.notes = item.notes
                if item.gender is not None:
                    existing.gender = _resolve_gender(item.gender, orig, trans, item.notes)
                if item.is_locked is not None:
                    existing.is_locked = item.is_locked
                existing.is_archived = bool(item.is_archived) if item.is_archived is not None else False
            else:
                db.add(LorebookEntry(
                    thread_id=thread_id,
                    original_term=orig,
                    translated_term=trans,
                    notes=item.notes,
                    gender=_resolve_gender(item.gender, orig, trans, item.notes),
                    is_locked=bool(item.is_locked) if item.is_locked is not None else False,
                    is_archived=bool(item.is_archived) if item.is_archived is not None else False,
                ))
            affected += 1
        if affected > 0:
            db.commit()
            enforce_context_limit(thread_id, db)
        return {"status": "ok", "action": body.action, "affected": affected}

    target_ids = body.entry_ids or []
    if not target_ids:
        return {"status": "ok", "action": body.action, "affected": 0}

    entries = db.execute(
        select(LorebookEntry).where(
            LorebookEntry.thread_id == thread_id,
            LorebookEntry.id.in_(target_ids)
        )
    ).scalars().all()

    for e in entries:
        if body.action == "lock":
            e.is_locked = True
            e.is_archived = False
            affected += 1
        elif body.action == "unlock":
            e.is_locked = False
            affected += 1
        elif body.action == "archive":
            e.is_archived = True
            e.is_locked = False
            affected += 1
        elif body.action == "restore":
            e.is_archived = False
            affected += 1
        elif body.action == "delete":
            db.delete(e)
            affected += 1

    db.commit()
    if body.action in ("unlock", "delete"):
        enforce_context_limit(thread_id, db)

    return {"status": "ok", "action": body.action, "affected": affected}


# ---------------------------------------------------------------------------
# Genre Preset Endpoints (ADR-073)
# ---------------------------------------------------------------------------

@router.get("/presets")
def list_presets():
    """List all available genre presets (cultivation ranks, wuxia terms, etc.)."""
    from services.genre_presets import list_presets as _list_presets
    return _list_presets()


@router.post("/threads/{thread_id}/presets/{preset_key}")
def apply_preset(
    thread_id: int,
    preset_key: str,
    body: PresetApplyRequest | None = None,
    db: Session = Depends(get_db),
):
    """Apply a genre preset to a thread's lorebook, synchronized with GlobalSetting.target_language."""
    from services.genre_presets import apply_preset as _apply_preset

    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, f"Thread {thread_id} not found")

    gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
    resolved_lang = (body.target_language if (body and body.target_language) else None) or (
        gs.target_language if (gs and gs.target_language) else "Indonesian"
    )
    lock_entries = body.lock_entries if body is not None else True

    result = _apply_preset(
        db,
        thread_id,
        preset_key,
        target_language=resolved_lang,
        lock_entries=lock_entries,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])

    enforce_context_limit(thread_id, db)
    return result
