"""
TXT Import Router (ADR-139).

Provides deterministic two-phase import pipeline:
1. POST /api/txt-import/preview: Strict decode, parse, and split drafts without DB writes.
2. POST /api/txt-import/confirm: Authoritative validation and atomic DB commit.
"""

from pathlib import Path
import re
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Chapter, Thread, get_db
from services.security import read_upload_limited
from services.txt_importer import (
    ParsedDraft,
    TxtDecodeError,
    TxtInvalidContentError,
    decode_txt_bytes,
    parse_txt_to_drafts,
)

# ADR-139 review limits
MAX_PREVIEW_BYTES = 10 * 1024 * 1024  # 10 MiB preview ceiling
MAX_REVIEW_CHARS = 5_000_000          # Bounded character count limit
MAX_REVIEW_DRAFTS = 1_000             # Bounded draft count limit

router = APIRouter(prefix="/api/txt-import", tags=["TXT Import"])


# ==========================================
# Pydantic Schemas
# ==========================================

class TargetPayload(BaseModel):
    mode: Literal["new", "existing"]
    thread_id: Optional[int] = None


class DraftItemPayload(BaseModel):
    title: str = Field(..., max_length=500)
    body: str
    source_chapter_ordinal: Optional[int] = None
    split_ordinal: Optional[int] = None
    split_total: Optional[int] = None


class ConfirmImportRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    target: TargetPayload
    drafts: List[DraftItemPayload]


# ==========================================
# Database Helper
# ==========================================

def _commit_import_transaction(
    db: Session,
    thread: Thread,
    chapters: List[Chapter],
) -> tuple[int, List[int]]:
    """Flushes and commits the thread and chapters atomically."""
    try:
        if thread.id is None:
            db.add(thread)
            db.flush()
        for ch in chapters:
            ch.thread_id = thread.id
            db.add(ch)
        db.flush()
        thread_id = thread.id
        chapter_ids = [ch.id for ch in chapters]
        db.commit()
        return thread_id, chapter_ids
    except Exception:
        db.rollback()
        raise


# ==========================================
# Endpoints
# ==========================================

@router.post("/preview")
async def preview_txt_import(file: UploadFile = File(...)):
    """
    Parses an uploaded .txt file into ordered, reviewable drafts.
    Performs strictly bounded decoding and chapter detection without DB writes.
    """
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="File must be a .txt file")

    raw_bytes = await read_upload_limited(file, max_bytes=MAX_PREVIEW_BYTES)

    try:
        text = decode_txt_bytes(raw_bytes)
    except (TxtInvalidContentError, TxtDecodeError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    if len(text) > MAX_REVIEW_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Total reviewable character count ({len(text)}) exceeds maximum limit of {MAX_REVIEW_CHARS} characters.",
        )

    try:
        parsed_drafts = parse_txt_to_drafts(text)
    except (TxtInvalidContentError, TxtDecodeError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    if len(parsed_drafts) > MAX_REVIEW_DRAFTS:
        raise HTTPException(
            status_code=422,
            detail=f"Total draft count ({len(parsed_drafts)}) exceeds maximum limit of {MAX_REVIEW_DRAFTS} drafts.",
        )

    raw_stem = Path(file.filename).stem
    clean_stem = re.sub(r"[^\w\s\-_]", "", raw_stem).strip()
    default_title = clean_stem if clean_stem else "Imported TXT"

    return {
        "title": default_title,
        "total_chapters": len(parsed_drafts),
        "total_words": sum(d.word_count for d in parsed_drafts),
        "drafts": [
            {
                "id": f"draft-{idx}",
                "title": d.title,
                "body": d.body,
                "source_chapter_ordinal": d.source_chapter_ordinal,
                "split_ordinal": d.split_ordinal,
                "split_total": d.split_total,
                "word_count": d.word_count,
                "is_oversized": d.is_oversized,
            }
            for idx, d in enumerate(parsed_drafts, start=1)
        ],
    }


@router.post("/confirm")
def confirm_txt_import(
    req: ConfirmImportRequest,
    db: Session = Depends(get_db),
):
    """
    Authoritatively validates user-confirmed drafts and commits records atomically.
    Modes:
    - 'new': Creates one Thread with source_type='txt' and all drafts as initial chapters.
    - 'existing': Appends drafts after the highest current Chapter.order without modifying thread metadata.
    """
    if not req.drafts:
        raise HTTPException(status_code=422, detail="Drafts list cannot be empty")

    if len(req.drafts) > MAX_REVIEW_DRAFTS:
        raise HTTPException(
            status_code=422,
            detail=f"Total draft count ({len(req.drafts)}) exceeds maximum limit of {MAX_REVIEW_DRAFTS} drafts.",
        )

    cleaned_drafts: List[tuple[str, str]] = []
    total_chars = 0
    for idx, draft in enumerate(req.drafts, start=1):
        clean_title = draft.title.strip()
        if not clean_title:
            raise HTTPException(
                status_code=422,
                detail=f"Draft {idx} has an empty or whitespace-only title",
            )
        if len(clean_title) > 500:
            raise HTTPException(
                status_code=422,
                detail=f"Draft {idx} title exceeds maximum limit of 500 characters",
            )
        clean_body = draft.body.strip()
        if not clean_body:
            raise HTTPException(
                status_code=422,
                detail=f"Draft {idx} has an empty or whitespace-only body",
            )
        total_chars += len(clean_body)
        cleaned_drafts.append((clean_title, clean_body))

    if total_chars > MAX_REVIEW_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Total character count ({total_chars}) exceeds maximum limit of {MAX_REVIEW_CHARS} characters.",
        )

    if req.target.mode == "new":
        raw_title = req.title if req.title is not None else ""
        confirmed_title = raw_title.strip() or "Imported TXT"
        if len(confirmed_title) > 500:
            raise HTTPException(
                status_code=422,
                detail="Title exceeds maximum limit of 500 characters",
            )
        raw_author = req.author if req.author is not None else ""
        confirmed_author = raw_author.strip() or None
        if confirmed_author and len(confirmed_author) > 200:
            raise HTTPException(
                status_code=422,
                detail="Author exceeds maximum limit of 200 characters",
            )
        target_thread = Thread(
            title=confirmed_title,
            original_title=confirmed_title,
            author=confirmed_author,
            source_type="txt",
        )
        start_order = 0
    elif req.target.mode == "existing":
        if req.target.thread_id is None:
            raise HTTPException(
                status_code=422,
                detail="thread_id is required when target mode is 'existing'",
            )
        target_thread = (
            db.query(Thread)
            .filter(Thread.id == req.target.thread_id)
            .first()
        )
        if not target_thread:
            raise HTTPException(
                status_code=404,
                detail=f"Target thread {req.target.thread_id} not found in active workspace",
            )
        max_order = (
            db.query(func.max(Chapter.order))
            .filter(Chapter.thread_id == target_thread.id)
            .scalar()
        )
        start_order = 0 if max_order is None else (max_order + 1)
    else:
        raise HTTPException(status_code=422, detail=f"Invalid target mode: {req.target.mode}")

    new_chapters: List[Chapter] = []
    for i, (title, body) in enumerate(cleaned_drafts):
        chapter = Chapter(
            thread_id=target_thread.id if target_thread.id else 0,
            order=start_order + i,
            title_original=title,
            title_translated=None,
            content_original=body,
            content_translated=None,
            translation_status="idle",
        )
        new_chapters.append(chapter)

    try:
        thread_id, chapter_ids = _commit_import_transaction(db, target_thread, new_chapters)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to commit import transaction: {e}",
        )

    return {
        "thread_id": thread_id,
        "chapter_ids": chapter_ids,
    }
