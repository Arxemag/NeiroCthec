import re
from core.models import Chapter, NormalizedBook


CHAPTER_RE = re.compile(r"^\s*(глава|chapter)\s+\d+", re.IGNORECASE)


class ChapterParser:
    """
    Stage 1.1 — ChapterParser
    """

    def parse(self, book: NormalizedBook) -> list[Chapter]:
        chapters = []
        current_lines = []
        chapter_index = 0
        current_title = None

        for line in book.lines:
            if CHAPTER_RE.match(line):
                if current_lines:
                    chapters.append(
                        Chapter(
                            index=chapter_index,
                            title=current_title,
                            lines=current_lines,
                        )
                    )
                    chapter_index += 1
                    current_lines = []

                current_title = line.strip()
            else:
                current_lines.append(line)

        if current_lines:
            chapters.append(
                Chapter(
                    index=chapter_index,
                    title=current_title,
                    lines=current_lines,
                )
            )

        return chapters
