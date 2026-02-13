from pathlib import Path


class FormatDetector:
    """
    Stage 0.1 — FormatDetector
    Определяет формат входного файла.
    """

    def detect(self, path: Path) -> str:
        ext = path.suffix.lower()

        if ext == ".txt":
            return "txt"
        if ext == ".fb2":
            return "fb2"

        raise ValueError(f"Unsupported format: {ext}")
