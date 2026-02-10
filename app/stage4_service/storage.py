from pathlib import Path


class LocalObjectStorage:
    """Локальное object storage для Stage 4 (stateless worker)."""

    def __init__(self, root: str = "storage/object", uri_prefix: str = "s3://audio"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.uri_prefix = uri_prefix.rstrip("/")

    def path_for_line(self, user_id: str, book_id: str, line_id: int) -> Path:
        target = self.root / user_id / book_id
        target.mkdir(parents=True, exist_ok=True)
        return target / f"line_{line_id}.wav"

    def uri_for_line(self, user_id: str, book_id: str, line_id: int) -> str:
        return f"{self.uri_prefix}/{user_id}/{book_id}/line_{line_id}.wav"
