from pydantic import BaseModel
from typing import List


class ChapterOut(BaseModel):
    chapter_id: int
    title: str


class BookUploadResponse(BaseModel):
    """Ответ загрузки книги. id — для фронта (NEXT_PUBLIC_APP_API_URL), book_id — то же значение для пайплайна."""
    book_id: str
    id: str  # дублирует book_id для совместимости с фронтом (data.id)
    status: str = "uploaded"
    chapters: List[ChapterOut]
