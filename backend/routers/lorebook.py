"""
Lorebook CRUD endpoints.
GET/POST /api/threads/{id}/lorebook
DELETE /api/lorebook/{entry_id}
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")

    return db.query(LorebookEntry).filter(
        LorebookEntry.thread_id == thread_id
    ).order_by(LorebookEntry.id).all()


@router.post("/threads/{thread_id}/lorebook", response_model=LorebookOut)
def create_lorebook_entry(
    thread_id: int,
    body: LorebookCreate,
    db: Session = Depends(get_db),
):
    """Add term to lorebook."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
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
    entry = db.query(LorebookEntry).filter(LorebookEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Entry not found")

    db.delete(entry)
    db.commit()
    return {"deleted": True, "id": entry_id}
