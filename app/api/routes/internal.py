from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.book import RetryBookPayload, RetryLinePayload, TTSCompletePayload, TTSLeaseResponse
from core.services.pipeline_service import run_contract_pipeline, try_stage5_assemble
from db.models import Book, Line, LineStatus, TTSTask, TaskStatus
from db.session import get_db

router = APIRouter()
OUTPUT_ROOT = Path("storage/audio")


@router.post("/tts-next", response_model=TTSLeaseResponse)
def tts_next(db: Session = Depends(get_db)):
    task = db.scalar(select(TTSTask).where(TTSTask.status == TaskStatus.pending).order_by(TTSTask.created_at.asc()))
    if not task:
        raise HTTPException(status_code=404, detail="No pending tasks")

    task.status = TaskStatus.processing
    db.commit()
    db.refresh(task)

    payload = task.payload
    return TTSLeaseResponse(
        task_id=task.id,
        line_id=payload["line_id"],
        user_id=payload["user_id"],
        book_id=payload["book_id"],
        text=payload["text"],
        voice=payload.get("voice", "narrator"),
        emotion=payload.get("emotion") or {},
    )


@router.post("/tts-complete")
def tts_complete(payload: TTSCompletePayload, db: Session = Depends(get_db)):
    line = db.scalar(select(Line).where(Line.id == payload.line_id))
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    line.audio_path = payload.audio_path
    line.tts_status = LineStatus.tts_done

    if line.tts_task:
        line.tts_task.status = TaskStatus.done

    book = db.scalar(select(Book).where(Book.id == line.book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    try_stage5_assemble(db, book, OUTPUT_ROOT)
    db.commit()
    return {"status": "ok", "line_id": line.id}


@router.post("/retry-line")
def retry_line(payload: RetryLinePayload, db: Session = Depends(get_db)):
    line = db.scalar(select(Line).where(Line.id == payload.line_id))
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    line.tts_status = LineStatus.tts_pending
    line.audio_path = None
    if line.tts_task:
        line.tts_task.status = TaskStatus.pending
    db.commit()
    return {"status": "scheduled", "line_id": line.id}


@router.post("/retry-book")
def retry_book(payload: RetryBookPayload, db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.id == payload.book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    run_contract_pipeline(db, book, OUTPUT_ROOT)
    db.commit()
    return {"status": "scheduled", "book_id": book.id}
