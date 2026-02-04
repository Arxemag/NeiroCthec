from dataclasses import dataclass
from typing import List, Optional


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

@dataclass(frozen=True)
class Line:
    id: int
    chapter_id: int
    type: str            # narrator | dialogue
    original: str        # IMMUTABLE


# ===== Stage 1.3–1.5 =====

@dataclass
class Segment:
    id: int
    line_id: int
    kind: str            # speech | remark | narration

    original_text: str   # ⊂ Line.original (immutable)
    char_start: int
    char_end: int

    # Stage 1.4
    tts_text: Optional[str] = None

    # Stage 1.5
    stress_map: Optional[dict] = None
