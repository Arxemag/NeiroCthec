# core/models.py
from dataclasses import dataclass
from typing import List, Optional, Dict


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
    tts_text: Optional[str] = None
    stress_map: Optional[dict] = None
    speaker: Optional[str] = None  # 🔥 ДОБАВЛЯЕМ СПИКЕРА ДЛЯ СЕГМЕНТОВ


@dataclass
class Remark:
    text: str
    position: str  # 'before' | 'after' | 'inline'


@dataclass
class UserBookFormat:
    lines: List[Line]
