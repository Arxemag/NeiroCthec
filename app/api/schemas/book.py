from pydantic import BaseModel
from typing import List


class ChapterOut(BaseModel):
    chapter_id: int
    title: str


class BookUploadResponse(BaseModel):
    book_id: int
    chapters: List[ChapterOut]
