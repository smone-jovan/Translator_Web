from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from database import get_db, CharacterRelationship, Thread
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api", tags=["Relationships"])

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
    stmt = select(CharacterRelationship).where(CharacterRelationship.thread_id == thread_id)
    relationships = db.execute(stmt).scalars().all()
    return relationships

@router.delete("/relationships/{rel_id}")
def delete_relationship(rel_id: int, db: Session = Depends(get_db)):
    rel = db.get(CharacterRelationship, rel_id)
    if not rel:
        raise HTTPException(404, "Relationship not found")
    db.delete(rel)
    db.commit()
    return {"status": "ok"}
