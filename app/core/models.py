# core/models.py
from dataclasses import dataclass
from typing import List, Optional, Dict, Literal


# ===== Stage 0 =====

@dataclass(frozen=True)
class NormalizedBook:
    raw_text: str
    lines: List[str]
    source_format: str


# ===== Stage 1.1 =====

@dataclass(frozen=True)
class Chapter:
    index: int
    title: Optional[str]
    lines: List[str]


# ===== Stage 1.2 =====

@dataclass
class Line:
    id: int
    chapter_id: int
    type: str            # narrator | dialogue
    original: str        # IMMUTABLE
    idx: Optional[int] = None  # 🔥 ДОБАВЛЯЕМ для сортировки в Stage 2
    remarks: List['Remark'] = None  # 🔥 ДОБАВЛЯЕМ для Stage 2
    is_segment: bool = False  # 🔥 ДОБАВЛЯЕМ
    base_line_id: Optional[int] = None  # 🔥 ДОБАВЛЯЕМ
    speaker: Optional[str] = None  # 🔥 ДОБАВЛЯЕМ ДЛЯ STAGE 2


# ===== Stage 1.3–1.5 =====

@dataclass
class Segment:
    id: int
    line_id: int
    kind: str
    original_text: str
    char_start: int
    char_end: int

    # === Stage 1.5 ===
    tts_text: Optional[str] = None
    stress_map: Optional[List[dict]] = None
    stress_applied: bool = False

    # === Stage 2+ ===
    speaker: Optional[str] = None

    # === Stage 3 ===
    speech_meta: Optional['SpeechMeta'] = None

    # 🔥 Stage 3 — дирижёр озвучки
    tts_meta: Optional[TTSMeta] = None


@dataclass
class Remark:
    text: str
    position: str  # 'before' | 'after' | 'inline'


@dataclass
class UserBookFormat:
    lines: List[Line]

# ===== Stage 3 =====

@dataclass
class SpeechMeta:
    # Просодия
    tempo: float = 1.0
    pitch: float = 0.0
    energy: float = 1.0
    volume: float = 1.0

    # Режимы
    whisper: bool = False

    # Паузы (мс)
    pause_before: int = 0
    pause_after: int = 0

    # Уважать ударения Stage 1.5
    respect_stress: bool = True

    # Отладка / причины
    tags: List[str] = None

TTSVolume = Literal["whisper", "quiet", "normal", "loud"]
TTSTempo = Literal["slow", "normal", "fast"]
TTSEmotion = Literal[
    "neutral",
    "sad",
    "angry",
    "happy",
    "fear",
    "irony",
    "tension"
]


@dataclass
class TTSMeta:
    volume: TTSVolume = "normal"
    tempo: TTSTempo = "normal"
    emotion: TTSEmotion = "neutral"

    emphasis: Optional[str] = None
    pause_before_ms: int = 0
    pause_after_ms: int = 0

    # чисто для дебага — ПОЧЕМУ принято решение
    reason: Optional[str] = None
