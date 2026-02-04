import re
from core.models import Line, Segment


REMARK_RE = re.compile(
    r'\b(?:сказал[а]?|ответил[а]?|спросил[а]?|'
    r'произнес[а]?|заметил[а]?|добавил[а]?|'
    r'прошептал[а]?|крикнул[а]?)\b',
    re.IGNORECASE
)

MAX_LEN = 182
TARGET_LEN = 100
MIN_LEN = 80


class SegmentAnalyzer:
    """
    Stage 1.3 — SegmentAnalyzer
    Разбивает Line.original на исполняемые сегменты.
    """

    def split(self, line: Line) -> list[Segment]:
        if line.type == "dialogue":
            return self._split_dialogue(line)
        return self._split_narration(line)

    def _split_dialogue(self, line: Line) -> list[Segment]:
        text = line.original
        segments = []
        seg_id = 0

        matches = list(REMARK_RE.finditer(text))
        if not matches:
            return [
                Segment(
                    id=0,
                    line_id=line.id,
                    kind="speech",
                    original_text=text,
                    char_start=0,
                    char_end=len(text),
                )
            ]

        last = 0
        for m in matches:
            if m.start() > last:
                segments.append(
                    Segment(
                        id=seg_id,
                        line_id=line.id,
                        kind="speech",
                        original_text=text[last:m.start()],
                        char_start=last,
                        char_end=m.start(),
                    )
                )
                seg_id += 1

            segments.append(
                Segment(
                    id=seg_id,
                    line_id=line.id,
                    kind="remark",
                    original_text=m.group(),
                    char_start=m.start(),
                    char_end=m.end(),
                )
            )
            seg_id += 1
            last = m.end()

        if last < len(text):
            segments.append(
                Segment(
                    id=seg_id,
                    line_id=line.id,
                    kind="speech",
                    original_text=text[last:],
                    char_start=last,
                    char_end=len(text),
                )
            )

        return segments

    def _split_narration(self, line: Line) -> list[Segment]:
        text = line.original
        segments = []
        start = 0
        seg_id = 0

        while start < len(text):
            end = min(start + MAX_LEN, len(text))
            cut = None

            for i in range(start + MIN_LEN, end):
                if text[i] in ".!?":
                    cut = i + 1
                    break

            if cut is None:
                cut = end

            segments.append(
                Segment(
                    id=seg_id,
                    line_id=line.id,
                    kind="narration",
                    original_text=text[start:cut],
                    char_start=start,
                    char_end=cut,
                )
            )

            seg_id += 1
            start = cut

        return segments
