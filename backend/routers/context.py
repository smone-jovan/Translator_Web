from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, GlobalSetting, Thread

router = APIRouter(prefix="/api", tags=["Context"])

class ContextUpdate(BaseModel):
    context: str

@router.get("/global-context")
def get_global_context(db: Session = Depends(get_db)):
    gs = db.query(GlobalSetting).first()
    return {"global_context": gs.global_context if gs else ""}

@router.post("/global-context")
def update_global_context(body: ContextUpdate, db: Session = Depends(get_db)):
    gs = db.query(GlobalSetting).first()
    if not gs:
        gs = GlobalSetting(global_context=body.context)
        db.add(gs)
    else:
        gs.global_context = body.context
    db.commit()
    return {"global_context": gs.global_context}

@router.get("/threads/{thread_id}/context")
def get_thread_context(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")
    return {"thread_context": thread.thread_context or ""}

@router.post("/threads/{thread_id}/context")
def update_thread_context(thread_id: int, body: ContextUpdate, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")
    thread.thread_context = body.context
    db.commit()
    return {"thread_context": thread.thread_context}
