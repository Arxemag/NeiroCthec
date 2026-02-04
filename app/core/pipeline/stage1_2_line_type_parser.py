import re
from core.models import Chapter, Line


DIALOGUE_START_RE = re.compile(r"^\s*[—–−]")


class LineTypeParser:
    """
    Stage 1.2 — LineTypeParser
    """

    def parse(self, chapters: list[Chapter]) -> list[Line]:
        lines: list[Line] = []
        line_id = 0

        for chapter in chapters:
            for raw in chapter.lines:
                text = raw.strip()
                if not text:
                    continue

                line_type = "dialogue" if DIALOGUE_START_RE.match(text) else "narrator"

                lines.append(
                    Line(
                        id=line_id,
                        chapter_id=chapter.index,
                        type=line_type,
                        original=text,
                    )
                )
                line_id += 1

        return lines
