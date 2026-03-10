# core/pipeline/stage2_post_chunk.py
"""
Постобработка после Stage 2 (SpeakerResolver): группировка по спикеру и chapter_id,
склейка текста и резание на чанки ~100 символов по границе точки, !, ?, пробела.
На выходе — новые линии с теми же полями speaker, chapter_id, type; новый idx и original.
"""

from typing import List

from core.models import Line, Remark, UserBookFormat


CHUNK_TARGET_CHARS = 100
CHUNK_MIN_CHARS = 80
CHUNK_MAX_CHARS = 182


def _find_split_pos(text: str, start: int) -> int:
    """
    Ищет позицию разбиения: сначала точка/!? в диапазоне [start+MIN, start+MAX],
    иначе режем по MAX. Возвращает индекс конца чанка.
    """
    end = min(start + CHUNK_MAX_CHARS, len(text))
    if len(text) - start <= CHUNK_MAX_CHARS:
        return len(text)
    cut = None
    scan_start = min(start + CHUNK_MIN_CHARS, len(text))
    for i in range(scan_start, end):
        if text[i] in ".!?":
            cut = i + 1
            break
    if cut is None:
        cut = end
    return cut


def _chunk_text(text: str) -> List[str]:
    """Режет текст на чанки ~100 символов по границе . ! ? (с допуском MIN/MAX)."""
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        cut = _find_split_pos(text, start)
        chunk = text[start:cut].strip()
        if chunk:
            chunks.append(chunk)
        start = cut
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

        # Заголовок главы — отдельной строкой, не склеиваем с текстом главы
        if is_chapter_header:
            t = (line.original or "").strip()
            if t:
                new_lines.append(
                    Line(
                        idx=next_idx,
                        type=line_type,
                        original=t,
                        remarks=[],
                        is_segment=False,
                        segment_index=None,
                        segment_total=None,
                        full_original=None,
                        base_line_id=next_idx,
                        chapter_id=chapter_id,
                        is_chapter_header=True,
                        speaker=speaker,
                        emotion=None,
                        audio_path=None,
                    )
                )
                next_idx += 1
            i += 1
            continue

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
            if getattr(L, "is_chapter_header", False):
                break
            t = (L.original or "").strip()
            if t:
                group_texts.append(t)
            group_chapter_header = group_chapter_header or getattr(L, "is_chapter_header", False)
            i += 1

        if not group_texts:
            continue

        block = " ".join(group_texts)
        chunks = _chunk_text(block)

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
