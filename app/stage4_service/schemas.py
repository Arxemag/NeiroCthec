from enum import Enum
from pydantic import BaseModel, Field


class TTSStatus(str, Enum):
    PENDING = "PENDING"
    IN_QUEUE = "IN_QUEUE"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    ERROR = "ERROR"


class EmotionPayload(BaseModel):
    energy: float = 1.0
    tempo: float = 1.0
    pitch: float = 0.0
    pause_before: int = 0
    pause_after: int = 0


class TTSRequest(BaseModel):
    task_id: str
    user_id: str
    book_id: str
    line_id: str
    text: str = Field(min_length=1)
    speaker: str = "narrator"
    emotion: EmotionPayload = Field(default_factory=EmotionPayload)


class TTSResponse(BaseModel):
    task_id: str
    status: TTSStatus
    audio_uri: str | None = None
    duration_ms: int | None = None
    error: str | None = None
