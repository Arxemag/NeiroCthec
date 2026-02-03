from fastapi import APIRouter, UploadFile, File
from pathlib import Path
import shutil
import uuid

from api.schemas.book import BookUploadResponse, ChapterOut

router = APIRouter()

STORAGE_ROOT = Path("storage")


@router.post("/upload", response_model=BookUploadResponse)
def upload_book(file: UploadFile = File(...)):
    book_id = uuid.uuid4().hex[:8]

    book_dir = STORAGE_ROOT / "books" / book_id
    original_dir = book_dir / "original"
    chapters_dir = book_dir / "chapters"

    original_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)

    original_path = original_dir / file.filename

    with original_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # ❗️ЗАГЛУШКА: тут позже Stage 1 + разбиение на главы
    chapters = [
        ChapterOut(chapter_id=1, title="Chapter 1")
    ]

    return BookUploadResponse(
        book_id=book_id,
        chapters=chapters
    )
