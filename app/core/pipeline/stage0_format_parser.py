from pathlib import Path


class FormatParser:
    """
    Stage 0.2 — FormatParser
    Загружает файл в raw-вид.
    """

    def parse(self, path: Path, fmt: str) -> str:
        if fmt in ("txt", "fb2"):
            return path.read_text(encoding="utf-8")

        raise ValueError(f"No parser for format: {fmt}")
