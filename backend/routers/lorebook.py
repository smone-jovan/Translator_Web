"""
Lorebook CRUD endpoints with limit cap, locked pinning, and archival compression.
GET/POST /api/threads/{id}/lorebook
DELETE /api/lorebook/{entry_id}
POST /api/lorebook/{entry_id}/lock
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from sqlalchemy import select, func
from database import get_db, LorebookEntry, Thread, GlobalSetting

router = APIRouter(prefix="/api", tags=["Lorebook"])


class LorebookCreate(BaseModel):
    original_term: str
    translated_term: str
    notes: str | None = None
    is_locked: bool | None = False
    is_archived: bool | None = False


class LorebookOut(BaseModel):
    id: int
    thread_id: int
    original_term: str
    translated_term: str
    notes: str | None
    is_locked: bool
    is_archived: bool

    model_config = ConfigDict(from_attributes=True)


class LockToggle(BaseModel):
    is_locked: bool


def enforce_context_limit(thread_id: int, db: Session):
    """
    Enforce global max_context_terms limit on active glossary entries of a thread.
    Locked entries are protected. Surplus active entries are archived (is_archived = True)
    and compressed (notes = None) using Least Frequently Used (usage_count ASC)
    with Least Recently Used (last_used_at ASC) as a tiebreaker.
    """
    # 1. Fetch global limit setting
    gs_stmt = select(GlobalSetting)
    gs = db.execute(gs_stmt).scalar_one_or_none()
    limit = gs.max_context_terms if gs else 50

    # 2. Get active entries for this thread
    active_stmt = (
        select(LorebookEntry)
        .where(LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False)
        .order_by(LorebookEntry.id)
    )
    active_entries = db.execute(active_stmt).scalars().all()

    if len(active_entries) <= limit:
        return

    # 3. surplus count
    surplus_count = len(active_entries) - limit

    # 4. Filter unlocked active entries
    evictable = [e for e in active_entries if not e.is_locked]

    # 5. Sort by usage_count ASC, then last_used_at/created_at ASC
    def sort_key(e):
        timestamp = e.last_used_at or e.created_at
        timestamp_val = timestamp.timestamp() if timestamp else 0
        return (e.usage_count, timestamp_val, e.id)

    evictable.sort(key=sort_key)

    # 6. Evict top surplus entries
    evict_list = evictable[:surplus_count]
    for entry in evict_list:
        entry.is_archived = True
        entry.notes = None  # Compress by deleting notes context
        
    db.commit()


@router.get("/threads/{thread_id}/lorebook", response_model=list[LorebookOut])
def list_lorebook(thread_id: int, db: Session = Depends(get_db)):
    """List all active (non-archived) lorebook entries for thread."""
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    entries_stmt = select(LorebookEntry).where(
        LorebookEntry.thread_id == thread_id,
        LorebookEntry.is_archived == False
    ).order_by(LorebookEntry.id)
    return db.execute(entries_stmt).scalars().all()


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

    # Case-insensitive check to restore or update if term already exists in DB
    existing_stmt = select(LorebookEntry).where(
        LorebookEntry.thread_id == thread_id,
        func.lower(LorebookEntry.original_term) == body.original_term.strip().lower()
    )
    existing_entry = db.execute(existing_stmt).scalars().first()
    if existing_entry:
        existing_entry.is_archived = False
        existing_entry.translated_term = body.translated_term
        existing_entry.notes = body.notes
        if body.is_locked is not None:
            existing_entry.is_locked = body.is_locked
        db.commit()
        db.refresh(existing_entry)
        
        enforce_context_limit(thread_id, db)
        db.refresh(existing_entry)
        return existing_entry

    entry = LorebookEntry(
        thread_id=thread_id,
        original_term=body.original_term,
        translated_term=body.translated_term,
        notes=body.notes,
        is_locked=body.is_locked if body.is_locked is not None else False,
        is_archived=body.is_archived if body.is_archived is not None else False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    enforce_context_limit(thread_id, db)
    db.refresh(entry)
    return entry


@router.delete("/lorebook/{entry_id}")
def delete_lorebook_entry(entry_id: int, db: Session = Depends(get_db)):
    """Delete lorebook entry."""
    stmt = select(LorebookEntry).where(LorebookEntry.id == entry_id)
    entry = db.execute(stmt).scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entry not found")

    db.delete(entry)
    db.commit()
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

    entry.original_term = body.original_term
    entry.translated_term = body.translated_term
    entry.notes = body.notes
    if body.is_locked is not None:
        entry.is_locked = body.is_locked
    if body.is_archived is not None:
        entry.is_archived = body.is_archived

    db.commit()
    db.refresh(entry)
    
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
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Genre Preset Endpoints (ADR-073)
# ---------------------------------------------------------------------------

@router.get("/presets")
def list_presets():
    """List all available genre presets (cultivation ranks, wuxia terms, etc.)."""
    from services.genre_presets import list_presets as _list_presets
    return _list_presets()


@router.post("/threads/{thread_id}/presets/{preset_key}")
def apply_preset(thread_id: int, preset_key: str, db: Session = Depends(get_db)):
    """Apply a genre preset to a thread's lorebook. Additive — does not overwrite existing entries."""
    from services.genre_presets import apply_preset as _apply_preset

    # Verify thread exists
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, f"Thread {thread_id} not found")

    result = _apply_preset(db, thread_id, preset_key)
    if "error" in result:
        raise HTTPException(400, result["error"])

    return result
