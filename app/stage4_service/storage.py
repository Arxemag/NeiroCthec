"""Хранение озвученных файлов в директории, доступной основному приложению (для сборки stage5)."""
import os
from pathlib import Path


def _storage_root() -> Path:
    root = os.getenv("CORE_STORAGE_PATH") or os.getenv("APP_STORAGE_ROOT")
    if root:
        return Path(root)
    # По умолчанию: app/storage относительно родителя stage4_service (app)
    return Path(__file__).resolve().parent.parent / "storage"


class LocalObjectStorage:
    """Сохраняет WAV по путям storage/books/{user_id}/{book_id}/lines/line_{line_id}.wav."""

    def __init__(self, base_path: Path | None = None):
        self.base = base_path or _storage_root()

    def path_for_line(self, user_id: str, book_id: str, line_id: int) -> Path:
        p = self.base / "books" / user_id / book_id / "lines" / f"line_{line_id}.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def uri_for_line(self, user_id: str, book_id: str, line_id: int) -> str:
        """Возвращает абсолютный путь к файлу (основное приложение использует его для stage5)."""
        return str(self.path_for_line(user_id, book_id, line_id).resolve())
