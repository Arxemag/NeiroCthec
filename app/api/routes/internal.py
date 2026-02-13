from __future__ import annotations

import os
from pathlib import Path

import requests
import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.book import (
    ProcessBookStage4Payload,
    ProcessBookStage4Response,
    RetryBookPayload,
    RetryLinePayload,
    StopBookStage4Payload,
    StopBookStage4Response,
    TTSCompletePayload,
    TTSLeaseResponse,
)
from core.services.pipeline_service import run_contract_pipeline, stage4_mark_done, try_stage5_assemble, update_book_status
from db.models import Book, Line, LineStatus, TTSTask, TaskStatus, UserAudioConfig
from db.session import get_db

router = APIRouter()
OUTPUT_ROOT = Path("storage/audio")
STAGE4_TTS_URL = os.getenv("STAGE4_TTS_URL", "http://stage4-tts:8010")
STOP_STAGE4_BOOKS: set[str] = set()
AUDIO_CONFIG_PATHS = (Path("audio.yaml"), Path("app/audio.yaml"))


def _load_global_audio_config() -> dict:
    for path in AUDIO_CONFIG_PATHS:
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
                if isinstance(loaded, dict):
                    return loaded
    return {}


def _merge_audio_config(base: dict, override: dict | None) -> dict:
    if not isinstance(base, dict):
        return override if isinstance(override, dict) else {}
    merged = dict(base)
    if not isinstance(override, dict):
        return merged

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_audio_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def _effective_audio_config(user_config: dict | None) -> dict:
    return _merge_audio_config(_load_global_audio_config(), user_config)


def _extract_language(audio_config: dict) -> str | None:
    """Извлекает язык из audio_config."""
    if not isinstance(audio_config, dict):
        return None
    engine = audio_config.get("engine")
    if isinstance(engine, dict):
        lang = engine.get("language")
        if isinstance(lang, str) and lang.strip():
            return lang.strip()
    return None

@router.post("/tts-next", response_model=TTSLeaseResponse)
def tts_next(db: Session = Depends(get_db)):
    task = db.scalar(select(TTSTask).where(TTSTask.status == TaskStatus.pending).order_by(TTSTask.created_at.asc()))
    if not task:
        raise HTTPException(status_code=404, detail="No pending tasks")

    task.status = TaskStatus.processing
    db.commit()
    db.refresh(task)

    payload = task.payload
    user_audio = db.scalar(select(UserAudioConfig).where(UserAudioConfig.user_id == payload["user_id"]))
    return TTSLeaseResponse(
        task_id=task.id,
        line_id=payload["line_id"],
        user_id=payload["user_id"],
        book_id=payload["book_id"],
        text=payload["text"],
        voice=payload.get("voice", "narrator"),
        emotion=payload.get("emotion") or {},
        audio_config=_effective_audio_config(user_audio.config if user_audio else None),
    )


@router.post("/tts-complete")
def tts_complete(payload: TTSCompletePayload, db: Session = Depends(get_db)):
    line = db.scalar(select(Line).where(Line.id == payload.line_id))
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    stage4_mark_done(db, line, payload.audio_path)

    book = db.scalar(select(Book).where(Book.id == line.book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    update_book_status(db, book)
    try_stage5_assemble(db, book, OUTPUT_ROOT)
    db.commit()
    return {"status": "ok", "line_id": line.id}


@router.post("/stop-book-stage4", response_model=StopBookStage4Response)
def stop_book_stage4(payload: StopBookStage4Payload):
    STOP_STAGE4_BOOKS.add(payload.book_id)
    return StopBookStage4Response(book_id=payload.book_id, stop_requested=True)


@router.post("/process-book-stage4", response_model=ProcessBookStage4Response)
def process_book_stage4(payload: ProcessBookStage4Payload, db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.id == payload.book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    processed = 0
    stopped = False
    user_audio = db.scalar(select(UserAudioConfig).where(UserAudioConfig.user_id == book.user_id))
    effective_audio_config = _effective_audio_config(user_audio.config if user_audio else None)
    language = _extract_language(effective_audio_config)
    for _ in range(max(payload.max_tasks, 1)):
        if book.id in STOP_STAGE4_BOOKS:
            STOP_STAGE4_BOOKS.discard(book.id)
            stopped = True
            break

        task = db.scalar(
            select(TTSTask)
            .join(Line, TTSTask.line_id == Line.id)
            .where(Line.book_id == book.id, TTSTask.status == TaskStatus.pending)
            .order_by(TTSTask.created_at.asc())
        )
        if not task:
            break

        payload_row = task.payload
        task.status = TaskStatus.processing
        db.commit()
        db.refresh(task)

        try:
            response = requests.post(
                f"{STAGE4_TTS_URL}/tts",
                json={
                    "task_id": task.id,
                    "user_id": payload_row["user_id"],
                    "book_id": payload_row["book_id"],
                    "line_id": payload_row["line_id"],
                    "text": payload_row["text"],
                    "speaker": payload_row.get("voice", "narrator"),
                    "emotion": payload_row.get("emotion") or {},
                    "audio_config": effective_audio_config,
                    "language": language,
                },
                timeout=120,
            )
            response.raise_for_status()
            tts_result = response.json()
        except Exception as exc:
            task.status = TaskStatus.error
            db.commit()
            raise HTTPException(status_code=502, detail=f"Stage4 call failed: {exc}") from exc

        if tts_result.get("status") != "DONE":
            task.status = TaskStatus.error
            db.commit()
            raise HTTPException(status_code=502, detail=f"Stage4 returned non-DONE: {tts_result}")

        line = db.scalar(select(Line).where(Line.id == payload_row["line_id"]))
        if not line:
            task.status = TaskStatus.error
            db.commit()
            raise HTTPException(status_code=404, detail=f"Line not found for task {task.id}")

        stage4_mark_done(db, line, tts_result.get("audio_uri") or "")
        processed += 1
        update_book_status(db, book)
        try_stage5_assemble(db, book, OUTPUT_ROOT)
        db.commit()

    remaining = db.scalar(
        select(func.count())
        .select_from(TTSTask)
        .join(Line, TTSTask.line_id == Line.id)
        .where(Line.book_id == book.id, TTSTask.status.in_([TaskStatus.pending, TaskStatus.processing]))
    ) or 0

    update_book_status(db, book)
    try_stage5_assemble(db, book, OUTPUT_ROOT)
    db.commit()
    db.refresh(book)

    return ProcessBookStage4Response(
        book_id=book.id,
        processed_tasks=processed,
        remaining_tasks=remaining,
        book_status=book.status.value,
        final_audio_path=book.final_audio_path,
        stopped=stopped,
    )


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
