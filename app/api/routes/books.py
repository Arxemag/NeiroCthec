from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_current_user_id
from api.schemas.book import (
    AudioConfigResponse,
    AudioConfigUpdatePayload,
    BookOut,
    BookStatusResponse,
    BookUploadResponse,
)
from core.services.pipeline_service import run_contract_pipeline, update_book_status
from db.models import Book, BookStatus, Line, LineStatus, UserAudioConfig
from db.session import get_db

router = APIRouter()

STORAGE_ROOT = Path("storage")
UPLOAD_ROOT = STORAGE_ROOT / "uploads"
OUTPUT_ROOT = STORAGE_ROOT / "audio"
AUDIO_CONFIG_PATHS = (Path("audio.yaml"), Path("app/audio.yaml"))
SUPPORTED_UPLOAD_EXTENSIONS = {".txt", ".fb2"}


def _load_global_audio_config() -> tuple[dict, str]:
    for path in AUDIO_CONFIG_PATHS:
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
                if not isinstance(loaded, dict):
                    raise HTTPException(status_code=500, detail="audio.yaml must contain a top-level object")
                return loaded, str(path)
    raise HTTPException(status_code=500, detail="audio.yaml was not found")


def _merge_audio_config(base: dict, override: dict | None) -> dict:
    merged = dict(base) if isinstance(base, dict) else {}
    if not isinstance(override, dict):
        return merged
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_audio_config(merged[key], value)
        else:
            merged[key] = value
    return merged


@router.post("/upload", response_model=BookUploadResponse)
def upload_book(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    book_id = str(uuid.uuid4())
    safe_name = file.filename or "book.txt"
    file_ext = Path(safe_name).suffix.lower()
    if file_ext not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Supported formats: .txt, .fb2")

    user_upload_root = UPLOAD_ROOT / user_id
    user_upload_root.mkdir(parents=True, exist_ok=True)
    source_path = user_upload_root / f"{book_id}_{safe_name}"

    with source_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    book = Book(id=book_id, user_id=user_id, title=safe_name, source_path=str(source_path))
    db.add(book)
    db.flush()

    try:
        run_contract_pipeline(db, book, OUTPUT_ROOT)
        db.commit()
    except (ValueError, UnicodeDecodeError) as exc:
        book.status = BookStatus.error
        db.commit()
        raise HTTPException(status_code=400, detail=f"Failed to parse uploaded file: {exc}") from exc
    except Exception as exc:
        book.status = BookStatus.error
        db.commit()
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}") from exc

    db.refresh(book)
    return BookUploadResponse(id=book.id, status=book.status.value)


@router.get("", response_model=list[BookOut])
def list_books(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    books = db.scalars(select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())).all()
    return [
        BookOut(
            id=b.id,
            title=b.title,
            status=b.status.value,
            created_at=b.created_at,
            final_audio_path=b.final_audio_path,
        )
        for b in books
    ]


@router.get("/settings/audio", response_model=AudioConfigResponse)
def get_audio_config(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    global_config, global_path = _load_global_audio_config()
    custom = db.scalar(select(UserAudioConfig).where(UserAudioConfig.user_id == user_id))
    if custom:
        return AudioConfigResponse(user_id=user_id, is_custom=True, source="user_db_merged", source_path="table:user_audio_configs + global_file", config=_merge_audio_config(global_config, custom.config))
    return AudioConfigResponse(user_id=user_id, is_custom=False, source="global_file", source_path=global_path, config=global_config)


@router.put("/settings/audio", response_model=AudioConfigResponse)
def upsert_audio_config(
    payload: AudioConfigUpdatePayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if not isinstance(payload.config, dict):
        raise HTTPException(status_code=400, detail="config must be an object")

    global_config, _ = _load_global_audio_config()
    row = db.scalar(select(UserAudioConfig).where(UserAudioConfig.user_id == user_id))
    if row:
        row.config = payload.config
    else:
        row = UserAudioConfig(user_id=user_id, config=payload.config)
        db.add(row)

    db.commit()
    db.refresh(row)
    return AudioConfigResponse(user_id=user_id, is_custom=True, source="user_db_merged", source_path="table:user_audio_configs + global_file", config=_merge_audio_config(global_config, row.config))


@router.delete("/settings/audio", response_model=AudioConfigResponse)
def reset_audio_config(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.scalar(select(UserAudioConfig).where(UserAudioConfig.user_id == user_id))
    if row:
        db.delete(row)
        db.commit()

    global_config, global_path = _load_global_audio_config()
    return AudioConfigResponse(user_id=user_id, is_custom=False, source="global_file", source_path=global_path, config=global_config)


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    update_book_status(db, book)
    db.commit()
    db.refresh(book)

    return BookOut(
        id=book.id,
        title=book.title,
        status=book.status.value,
        created_at=book.created_at,
        final_audio_path=book.final_audio_path,
    )


@router.delete("/{book_id}")
def delete_book(book_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(book)
    db.commit()
    return {"status": "deleted", "book_id": book_id}


@router.get("/{book_id}/status", response_model=BookStatusResponse)
def get_book_status(book_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    total = db.scalar(select(func.count()).select_from(Line).where(Line.book_id == book.id)) or 0
    done = db.scalar(
        select(func.count()).select_from(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.tts_done)
    ) or 0

    progress = int((done / total) * 100) if total else 0
    stage = "stage5" if book.status.value == "assembling" else book.status.value
    return BookStatusResponse(stage=stage, progress=progress, total_lines=total, tts_done=done)


@router.get("/{book_id}/download")
def download_book_audio(book_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.final_audio_path or not Path(book.final_audio_path).exists():
        raise HTTPException(status_code=409, detail="Final audio is not ready")

    final_path = Path(book.final_audio_path)
    media_type = "audio/wav" if final_path.suffix.lower() == ".wav" else "audio/mpeg"
    return FileResponse(path=book.final_audio_path, filename=f"{book.id}{final_path.suffix}", media_type=media_type)


