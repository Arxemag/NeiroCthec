"""Test routes for book TTS without authentication."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import Depends

from api.schemas.book import BookStatusResponse, BookUploadResponse
from core.services.pipeline_service import run_contract_pipeline, update_book_status
from db.models import Book, BookStatus, Line, LineStatus
from db.session import get_db

router = APIRouter()

STORAGE_ROOT = Path("storage")
UPLOAD_ROOT = STORAGE_ROOT / "uploads"
OUTPUT_ROOT = STORAGE_ROOT / "audio"

# Test user ID for anonymous uploads
TEST_USER_ID = "test-anonymous-user"


@router.post("/upload", response_model=BookUploadResponse)
def test_upload_book(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a book for TTS processing without authentication."""
    book_id = str(uuid.uuid4())
    safe_name = file.filename or "book.txt"

    user_upload_root = UPLOAD_ROOT / TEST_USER_ID
    user_upload_root.mkdir(parents=True, exist_ok=True)
    source_path = user_upload_root / f"{book_id}_{safe_name}"

    with source_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    book = Book(id=book_id, user_id=TEST_USER_ID, title=safe_name, source_path=str(source_path))
    db.add(book)
    db.flush()

    # Run stages 0-3 synchronously
    run_contract_pipeline(db, book, OUTPUT_ROOT)
    db.commit()
    db.refresh(book)
    return BookUploadResponse(id=book.id, status=book.status.value)


@router.get("/{book_id}/status", response_model=BookStatusResponse)
def test_get_book_status(book_id: str, db: Session = Depends(get_db)):
    """Get the current status of a test book."""
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == TEST_USER_ID))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    update_book_status(db, book)
    db.commit()

    total = db.scalar(select(func.count()).select_from(Line).where(Line.book_id == book.id)) or 0
    done = db.scalar(
        select(func.count()).select_from(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.tts_done)
    ) or 0

    progress = int((done / total) * 100) if total else 0
    
    # Map status to stage
    stage_map = {
        BookStatus.uploaded: "stage0",
        BookStatus.parsing: "stage1",
        BookStatus.analyzed: "stage3",
        BookStatus.tts_processing: "stage4",
        BookStatus.assembling: "stage5",
        BookStatus.completed: "completed",
        BookStatus.error: "error",
    }
    stage = stage_map.get(book.status, book.status.value)
    
    return BookStatusResponse(stage=stage, progress=progress, total_lines=total, tts_done=done)


class ChapterInfo:
    def __init__(self, chapter_id: int, title: str, audio_url: str | None, status: str, lines_done: int, lines_total: int):
        self.chapter_id = chapter_id
        self.title = title
        self.audio_url = audio_url
        self.status = status
        self.lines_done = lines_done
        self.lines_total = lines_total


@router.get("/{book_id}/chapters")
def test_get_chapters(book_id: str, db: Session = Depends(get_db)):
    """Get chapters with their audio status for a test book."""
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == TEST_USER_ID))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    lines = db.scalars(select(Line).where(Line.book_id == book.id).order_by(Line.idx.asc())).all()
    
    # Group lines by chapter
    chapters_data: dict[int, dict] = {}
    for line in lines:
        chapter_id = 0
        if line.segments and isinstance(line.segments, list) and len(line.segments) > 0:
            first_seg = line.segments[0]
            if isinstance(first_seg, dict):
                chapter_id = first_seg.get("chapter_id", 0)
        
        if chapter_id not in chapters_data:
            chapters_data[chapter_id] = {
                "chapter_id": chapter_id,
                "title": f"Глава {chapter_id}" if chapter_id > 0 else "Введение",
                "lines": [],
                "lines_done": 0,
                "lines_total": 0,
            }
        
        chapters_data[chapter_id]["lines"].append(line)
        chapters_data[chapter_id]["lines_total"] += 1
        if line.tts_status == LineStatus.tts_done or line.tts_status == LineStatus.assembled:
            chapters_data[chapter_id]["lines_done"] += 1

    # Build response
    chapters = []
    for chapter_id in sorted(chapters_data.keys()):
        ch = chapters_data[chapter_id]
        status = "pending"
        if ch["lines_done"] == ch["lines_total"] and ch["lines_total"] > 0:
            status = "ready"
        elif ch["lines_done"] > 0:
            status = "processing"
        
        # Check if chapter audio file exists
        chapter_audio_path = OUTPUT_ROOT / TEST_USER_ID / book_id / "chapters" / f"chapter_{chapter_id:03d}.mp3"
        audio_url = f"/test/{book_id}/chapters/{chapter_id}/audio" if chapter_audio_path.exists() or status == "ready" else None
        
        chapters.append({
            "chapter_id": chapter_id,
            "title": ch["title"],
            "audio_url": audio_url,
            "status": status,
            "lines_done": ch["lines_done"],
            "lines_total": ch["lines_total"],
        })

    return {"chapters": chapters, "book_status": book.status.value}


@router.get("/{book_id}/chapters/{chapter_id}/audio")
def test_get_chapter_audio(book_id: str, chapter_id: int, db: Session = Depends(get_db)):
    """Download audio for a specific chapter."""
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == TEST_USER_ID))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Get lines for this chapter
    lines = db.scalars(select(Line).where(Line.book_id == book.id).order_by(Line.idx.asc())).all()
    
    chapter_lines = []
    for line in lines:
        line_chapter_id = 0
        if line.segments and isinstance(line.segments, list) and len(line.segments) > 0:
            first_seg = line.segments[0]
            if isinstance(first_seg, dict):
                line_chapter_id = first_seg.get("chapter_id", 0)
        
        if line_chapter_id == chapter_id and line.audio_path:
            chapter_lines.append(line)

    if not chapter_lines:
        raise HTTPException(status_code=404, detail="Chapter audio not ready")

    # Return first available audio for now (in production, concatenate all)
    first_audio = chapter_lines[0].audio_path
    if first_audio and Path(first_audio).exists():
        return FileResponse(path=first_audio, filename=f"chapter_{chapter_id}.mp3", media_type="audio/mpeg")
    
    raise HTTPException(status_code=404, detail="Audio file not found")


@router.get("/{book_id}/lines")
def test_get_lines(book_id: str, db: Session = Depends(get_db)):
    """Get all lines with their audio status for a test book."""
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == TEST_USER_ID))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    lines = db.scalars(select(Line).where(Line.book_id == book.id).order_by(Line.idx.asc())).all()
    
    return {
        "lines": [
            {
                "id": line.id,
                "idx": line.idx,
                "text": line.original,
                "speaker": line.speaker,
                "status": line.tts_status.value,
                "audio_url": f"/test/{book_id}/lines/{line.id}/audio" if line.audio_path else None,
                "chapter_id": line.segments[0].get("chapter_id", 0) if line.segments and isinstance(line.segments, list) and len(line.segments) > 0 else 0,
            }
            for line in lines
        ]
    }


@router.get("/{book_id}/lines/{line_id}/audio")
def test_get_line_audio(book_id: str, line_id: str, db: Session = Depends(get_db)):
    """Download audio for a specific line."""
    line = db.scalar(select(Line).where(Line.id == line_id, Line.book_id == book_id))
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    # Verify book belongs to test user
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == TEST_USER_ID))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not line.audio_path or not Path(line.audio_path).exists():
        raise HTTPException(status_code=404, detail="Audio not ready")

    return FileResponse(path=line.audio_path, filename=f"line_{line.idx}.mp3", media_type="audio/mpeg")


@router.get("/{book_id}/download")
def test_download_full_audio(book_id: str, db: Session = Depends(get_db)):
    """Download the complete audio file for a test book."""
    book = db.scalar(select(Book).where(Book.id == book_id, Book.user_id == TEST_USER_ID))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book.final_audio_path or not Path(book.final_audio_path).exists():
        raise HTTPException(status_code=409, detail="Final audio is not ready")

    return FileResponse(path=book.final_audio_path, filename=f"{book.id}.mp3", media_type="audio/mpeg")
