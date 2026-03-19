from pydantic import BaseModel


class ChapterProcessResponse(BaseModel):
    chapter_id: int
    status: str
    audio_path: str | None = None
