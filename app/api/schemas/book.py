from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BookOut(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime
    final_audio_path: str | None = None


class BookUploadResponse(BaseModel):
    id: str
    status: str


class BookStatusResponse(BaseModel):
    stage: str
    progress: int
    total_lines: int
    tts_done: int


class TTSCompletePayload(BaseModel):
    line_id: str
    audio_path: str


class RetryLinePayload(BaseModel):
    line_id: str


class RetryBookPayload(BaseModel):
    book_id: str


class TTSLeaseResponse(BaseModel):
    task_id: str
    line_id: str
    user_id: str
    book_id: str
    text: str
    voice: str
    emotion: dict
    audio_config: dict | None = None



class AudioConfigResponse(BaseModel):
    user_id: str
    is_custom: bool
    config: dict


class AudioConfigUpdatePayload(BaseModel):
    config: dict
