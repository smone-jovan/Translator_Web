from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete
from typing import List

from database import get_db, CharacterRelationship, Thread
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api", tags=["Relationships"])


class RelationshipCreate(BaseModel):
    source_term: str
    target_term: str
    relationship_type: str
    notes: str | None = None


class RelationshipUpdate(BaseModel):
    source_term: str | None = None
    target_term: str | None = None
    relationship_type: str | None = None
    notes: str | None = None


class RelationshipResponse(BaseModel):
    id: int
    thread_id: int
    source_term: str
    target_term: str
    relationship_type: str
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/threads/{thread_id}/relationships", response_model=List[RelationshipResponse])
def get_relationships(thread_id: int, db: Session = Depends(get_db)):
    stmt = select(CharacterRelationship).where(CharacterRelationship.thread_id == thread_id).order_by(CharacterRelationship.id)
    relationships = db.execute(stmt).scalars().all()
    return relationships


@router.post("/threads/{thread_id}/relationships", response_model=RelationshipResponse)
def create_relationship(thread_id: int, body: RelationshipCreate, db: Session = Depends(get_db)):
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    src = body.source_term.strip()
    tgt = body.target_term.strip()
    rel_type = body.relationship_type.strip()
    if not src or not tgt or not rel_type:
        raise HTTPException(400, "source_term, target_term, and relationship_type are required")

    existing = db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.thread_id == thread_id,
            func.lower(CharacterRelationship.source_term) == src.lower(),
            func.lower(CharacterRelationship.target_term) == tgt.lower(),
        )
    ).scalars().first()

    if existing:
        existing.source_term = src
        existing.target_term = tgt
        existing.relationship_type = rel_type
        existing.notes = body.notes
        db.commit()
        db.refresh(existing)
        return existing

    rel = CharacterRelationship(
        thread_id=thread_id,
        source_term=src,
        target_term=tgt,
        relationship_type=rel_type,
        notes=body.notes,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.put("/relationships/{rel_id}", response_model=RelationshipResponse)
def update_relationship(rel_id: int, body: RelationshipUpdate, db: Session = Depends(get_db)):
    rel = db.get(CharacterRelationship, rel_id)
    if not rel:
        raise HTTPException(404, "Relationship not found")

    if body.source_term is not None and body.source_term.strip():
        rel.source_term = body.source_term.strip()
    if body.target_term is not None and body.target_term.strip():
        rel.target_term = body.target_term.strip()
    if body.relationship_type is not None and body.relationship_type.strip():
        rel.relationship_type = body.relationship_type.strip()
    if body.notes is not None:
        rel.notes = body.notes

    db.commit()
    db.refresh(rel)
    return rel


@router.delete("/relationships/{rel_id}")
def delete_relationship(rel_id: int, db: Session = Depends(get_db)):
    rel = db.get(CharacterRelationship, rel_id)
    if not rel:
        raise HTTPException(404, "Relationship not found")
    db.delete(rel)
    db.commit()
    return {"status": "ok", "id": rel_id}


@router.delete("/threads/{thread_id}/relationships")
def clear_thread_relationships(thread_id: int, db: Session = Depends(get_db)):
    thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    res = db.execute(delete(CharacterRelationship).where(CharacterRelationship.thread_id == thread_id))
    db.commit()
    return {"status": "ok", "deleted_count": res.rowcount or 0}
