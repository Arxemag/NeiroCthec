"""Схемы для Stage4 TTS Worker."""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class TTSStatus(str, Enum):
    DONE = "done"
    ERROR = "error"


class TTSRequest(BaseModel):
    task_id: str
    user_id: str
    book_id: str
    line_id: int
    text: str
    speaker: str  # narrator | male | female
    emotion: Optional[dict[str, Any]] = None
    audio_config: Optional[dict[str, Any]] = None


class TTSResponse(BaseModel):
    task_id: str
    status: TTSStatus
    audio_uri: Optional[str] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
