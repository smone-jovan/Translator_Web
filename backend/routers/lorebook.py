"""
Lorebook CRUD endpoints.
GET/POST /api/threads/{id}/lorebook
DELETE /api/lorebook/{entry_id}
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import select
from database import get_db, LorebookEntry, Thread

router = APIRouter(prefix="/api", tags=["Lorebook"])


class LorebookCreate(BaseModel):
    original_term: str
    translated_term: str
    notes: str | None = None


class LorebookOut(BaseModel):
    id: int
    thread_id: int
    original_term: str
    translated_term: str
    notes: str | None

    class Config:
        from_attributes = True


@router.get("/threads/{thread_id}/lorebook", response_model=list[LorebookOut])
def list_lorebook(thread_id: int, db: Session = Depends(get_db)):
    """List all lorebook entries for thread."""
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    entries_stmt = select(LorebookEntry).where(LorebookEntry.thread_id == thread_id).order_by(LorebookEntry.id)
    return db.execute(entries_stmt).scalars().all()


@router.post("/threads/{thread_id}/lorebook", response_model=LorebookOut)
def create_lorebook_entry(
    thread_id: int,
    body: LorebookCreate,
    db: Session = Depends(get_db),
):
    """Add term to lorebook."""
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    entry = LorebookEntry(
        thread_id=thread_id,
        original_term=body.original_term,
        translated_term=body.translated_term,
        notes=body.notes,
    )
    db.add(entry)
    db.commit()
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
    """Update an existing lorebook entry."""
    stmt = select(LorebookEntry).where(LorebookEntry.id == entry_id)
    entry = db.execute(stmt).scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entry not found")

    entry.original_term = body.original_term
    entry.translated_term = body.translated_term
    entry.notes = body.notes

    db.commit()
    db.refresh(entry)
    return entry
