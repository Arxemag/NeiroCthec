import os
from pathlib import Path

import shutil
import uuid
from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from api.schemas.book import BookUploadResponse, ChapterOut
from core.book_convert import book_to_text

router = APIRouter()

ALLOWED_BOOK_EXTENSIONS = (".txt", ".fb2", ".epub", ".mobi")
EXTRACTED_TXT = "extracted.txt"

# Относительно корня app/ (как в core.voices)
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
_storage_env = os.environ.get("APP_STORAGE_ROOT") or os.environ.get("CORE_STORAGE_PATH")
STORAGE_ROOT = Path(_storage_env) if _storage_env else _APP_ROOT / "storage"


_PROJECT_ID_FILE = ".project_id"


def _find_existing_book_dir(user_id: str, filename: str, project_id: str | None = None) -> Path | None:
    """
    Ищем уже загруженную книгу для пользователя по имени файла и опционально по project_id.
    Если передан project_id, переиспользуем только папку с тем же .project_id.
    """
    base = STORAGE_ROOT / "books" / user_id
    if not base.exists():
        return None
    for candidate in base.iterdir():
        if not candidate.is_dir():
            continue
        orig = candidate / "original" / filename
        if not orig.exists():
            continue
        if project_id:
            pid_file = candidate / _PROJECT_ID_FILE
            if pid_file.exists():
                try:
                    if pid_file.read_text(encoding="utf-8").strip() == project_id:
                        return candidate
                except Exception:
                    pass
            continue
        return candidate
    return None


@router.post("/upload", response_model=BookUploadResponse)
def upload_book(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    x_project_id: str | None = Header(None, alias="X-Project-Id"),
):
    """
    Загрузка файла книги: .txt, .fb2, .epub, .mobi.
    X-User-Id — id пользователя. X-Project-Id — id проекта (Nest), чтобы при удалении проекта удалить и книги.
    """
    user_id = (x_user_id or "").strip() or "anonymous"
    project_id = (x_project_id or "").strip() or None
    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_BOOK_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(ALLOWED_BOOK_EXTENSIONS)}",
        )

    existing_dir = _find_existing_book_dir(user_id, filename, project_id)
    if existing_dir is not None:
        book_dir = existing_dir
        book_id = existing_dir.name
    else:
        book_id = uuid.uuid4().hex[:8]
        book_dir = STORAGE_ROOT / "books" / user_id / book_id

    original_dir = book_dir / "original"
    chapters_dir = book_dir / "chapters"

    original_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)

    original_path = original_dir / filename

    with original_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    if suffix in (".fb2", ".epub", ".mobi"):
        try:
            text = book_to_text(original_path)
            (original_dir / EXTRACTED_TXT).write_text(text, encoding="utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Не удалось извлечь текст из файла: {e!s}",
            ) from e

    if project_id:
        (book_dir / _PROJECT_ID_FILE).write_text(project_id, encoding="utf-8")

    chapters = [
        ChapterOut(chapter_id=1, title="Chapter 1")
    ]

    return BookUploadResponse(
        book_id=book_id,
        id=book_id,
        status="uploaded",
        chapters=chapters,
    )


@router.delete("/by-project/{project_id}")
def delete_books_by_project(
    project_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    Удаляет все книги, привязанные к проекту (папки с .project_id == project_id).
    Вызывать перед удалением проекта в Nest. Важно: маршрут должен быть выше /{book_id}.
    """
    user_id = (x_user_id or "").strip() or "anonymous"
    base = (STORAGE_ROOT / "books" / user_id).resolve()
    if not base.exists():
        return {"status": "deleted", "deleted_count": 0, "book_ids": []}
    deleted = []
    for candidate in list(base.iterdir()):
        if not candidate.is_dir():
            continue
        try:
            target = candidate.resolve()
            target.relative_to(base)
        except ValueError:
            continue
        pid_file = target / _PROJECT_ID_FILE
        if not pid_file.exists():
            continue
        try:
            if pid_file.read_text(encoding="utf-8").strip() != project_id:
                continue
        except Exception:
            continue
        shutil.rmtree(target, ignore_errors=True)
        deleted.append(candidate.name)
    return {"status": "deleted", "deleted_count": len(deleted), "book_ids": deleted}


@router.delete("/{book_id}")
def delete_book(
    book_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    Удаляет книгу с сервера (папку storage/books/{user_id}/{book_id}).
    Удалять можно только свои книги (по X-User-Id).
    """
    user_id = (x_user_id or "").strip() or "anonymous"
    base = (STORAGE_ROOT / "books" / user_id).resolve()
    book_dir = (base / book_id).resolve()
    if not book_dir.exists() or not book_dir.is_dir():
        raise HTTPException(status_code=404, detail="Book not found")
    try:
        book_dir.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=404, detail="Book not found")
    shutil.rmtree(book_dir, ignore_errors=True)
    return {"status": "deleted", "book_id": book_id}
