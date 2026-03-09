# core/pipeline/stage2_post_chunk.py
"""
Постобработка после Stage 2 (SpeakerResolver): группировка по спикеру и chapter_id,
склейка текста и резание на чанки ~100 символов по границе точки, !, ?, пробела.
На выходе — новые линии с теми же полями speaker, chapter_id, type; новый idx и original.
"""

import re
from typing import List

from core.models import Line, Remark, UserBookFormat


CHUNK_TARGET_CHARS = 100
# Порядок поиска границы: точка, ! ?, пробел
BOUNDARY_RE = re.compile(r"[.!?]\s*|\s+")


def _find_split_pos(text: str, target: int) -> int:
    """
    Ищет позицию разбиения около target: сначала точка (до/после 100-го символа),
    затем ! или ?, затем пробел. Возвращает длину первого чанка (включительно до границы).
    """
    if len(text) <= target:
        return len(text)
    search_region = text[max(0, target - 50) : target + 51]
    best = -1
    best_priority = -1
    for m in BOUNDARY_RE.finditer(search_region):
        # Предпочтение: . = 3, !? = 2, пробел = 1
        start = m.start() + max(0, target - 50)
        char = text[start : start + 1] if start < len(text) else ""
        if char in ".!?":
            priority = 3 if char == "." else 2
        else:
            priority = 1
        if priority > best_priority or (priority == best_priority and abs(start - target) < abs(best - target)):
            best = start + len(m.group(0).rstrip())  # конец предложения/слова для первого чанка
            best_priority = priority
    if best > 0:
        return best
    # Fallback: режем по пробелу около target
    space_pos = text.rfind(" ", max(0, target - 30), min(len(text), target + 31))
    if space_pos > 0:
        return space_pos + 1
    return min(target, len(text))


def _chunk_text(text: str, target_chars: int = CHUNK_TARGET_CHARS) -> List[str]:
    """Режет текст на чанки ~target_chars по границе . ! ? пробел."""
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    rest = text
    while rest:
        rest = rest.strip()
        if not rest:
            break
        if len(rest) <= target_chars:
            chunks.append(rest)
            break
        pos = _find_split_pos(rest, target_chars)
        chunks.append(rest[:pos].strip())
        rest = rest[pos:]
    return [c for c in chunks if c]


def process(ubf: UserBookFormat) -> None:
    """
    После Stage 2: группирует подряд идущие строки с одним спикером и chapter_id,
    склеивает текст, режет на чанки ~100 символов. Заменяет ubf.lines на новые линии
    (новые idx, original; speaker, chapter_id, type сохраняются).
    """
    if not ubf.lines:
        return

    sorted_lines = sorted(ubf.lines, key=lambda l: (l.idx, getattr(l, "segment_index") or 0))
    new_lines: List[Line] = []
    next_idx = 0

    i = 0
    while i < len(sorted_lines):
        line = sorted_lines[i]
        speaker = line.speaker or "narrator"
        chapter_id = line.chapter_id if line.chapter_id is not None else 1
        line_type = line.type or "narrator"
        is_chapter_header = getattr(line, "is_chapter_header", False)

        # Группа: все подряд с тем же speaker и chapter_id
        group_texts = []
        group_type = line_type
        group_chapter_header = is_chapter_header
        while i < len(sorted_lines):
            L = sorted_lines[i]
            sp = L.speaker or "narrator"
            ch = L.chapter_id if L.chapter_id is not None else 1
            if sp != speaker or ch != chapter_id:
                break
            t = (L.original or "").strip()
            if t:
                group_texts.append(t)
            group_chapter_header = group_chapter_header or getattr(L, "is_chapter_header", False)
            i += 1

        if not group_texts:
            continue

        block = " ".join(group_texts)
        chunks = _chunk_text(block, CHUNK_TARGET_CHARS)

        for j, chunk in enumerate(chunks):
            first_in_group = j == 0
            new_lines.append(
                Line(
                    idx=next_idx,
                    type=group_type,
                    original=chunk,
                    remarks=[],
                    is_segment=False,
                    segment_index=None,
                    segment_total=None,
                    full_original=None,
                    base_line_id=next_idx,
                    chapter_id=chapter_id,
                    is_chapter_header=group_chapter_header and first_in_group,
                    speaker=speaker,
                    emotion=None,
                    audio_path=None,
                )
            )
            next_idx += 1

    ubf.lines = new_lines
