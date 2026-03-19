# core/models.py
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class SpeakerType(Enum):
    NARRATOR = "narrator"
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class EmotionProfile:
    energy: float = 1.0
    tempo: float = 1.0
    pitch: float = 0.0
    pause_before: int = 0
    pause_after: int = 0


@dataclass(slots=True)
class Remark:
    text: str


@dataclass(slots=True)
class Line:
    # Основные поля
    idx: int
    type: str  # "dialogue" или "narrator"
    original: str
    remarks: List[Remark]

    # Поля для сегментов (ДОБАВЛЯЕМ СЮДА!)
    is_segment: bool = False
    segment_index: Optional[int] = None
    segment_total: Optional[int] = None
    full_original: Optional[str] = None
    base_line_id: Optional[int] = None

    # Глава (по заголовкам в парсере)
    chapter_id: Optional[int] = None  # 1 = первая глава / без явного заголовка
    is_chapter_header: bool = False  # True если строка — заголовок главы (CHAPTER_HEADER_RE)

    # Результаты обработки
    speaker: Optional[str] = None  # "male", "female", "narrator"
    emotion: Optional[EmotionProfile] = None
    audio_path: Optional[str] = None

    # Текст для TTS после нормализации (кавычки, троеточия и т.д.); заполняется после Stage 3
    text_for_tts: Optional[str] = None

    # Внутренние флаги (не slots, используем property)
    @property
    def _logged(self) -> bool:
        return getattr(self, '__logged', False)

    @_logged.setter
    def _logged(self, value: bool):
        setattr(self, '__logged', value)


@dataclass(slots=True)
class UserBookFormat:
    user_id: int
    book_id: int
    version: str
    lines: List[Line]