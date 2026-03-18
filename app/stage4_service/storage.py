"""Хранение озвученных файлов: локально (для сборки stage5) + опционально в S3/MinIO."""
import os
from pathlib import Path


def _storage_root() -> Path:
    root = os.getenv("CORE_STORAGE_PATH") or os.getenv("APP_STORAGE_ROOT")
    if root:
        return Path(root)
    # По умолчанию: app/storage относительно родителя stage4_service (app)
    return Path(__file__).resolve().parent.parent / "storage"


class LocalObjectStorage:
    """Сохраняет WAV по путям storage/books/{user_id}/{book_id}/lines/line_{line_id}.wav."""

    def __init__(self, base_path: Path | None = None):
        self.base = base_path or _storage_root()

    def path_for_line(self, user_id: str, book_id: str, line_id: int) -> Path:
        p = self.base / "books" / user_id / book_id / "lines" / f"line_{line_id}.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def uri_for_line(self, user_id: str, book_id: str, line_id: int) -> str:
        """Путь относительно корня storage (books/.../lines/line_N.wav), чтобы Core API в Docker и на хосте разрешали его через свой STORAGE_ROOT."""
        p = self.path_for_line(user_id, book_id, line_id)
        try:
            return str(p.relative_to(self.base))
        except ValueError:
            return str(p.resolve())

    def path_for_preview(self, user_id: str, book_id: str, role: str) -> Path:
        """Путь для превью по спикеру: books/{user_id}/{book_id}/preview_{role}.wav."""
        p = self.base / "books" / user_id / book_id / f"preview_{role}.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def uri_for_preview(self, user_id: str, book_id: str, role: str) -> str:
        """URI превью относительно корня storage."""
        p = self.path_for_preview(user_id, book_id, role)
        try:
            return str(p.relative_to(self.base))
        except ValueError:
            return str(p.resolve())


class S3ObjectStorage:
    """S3/MinIO uploader. Не заменяет локальную запись: core assembly читает локальные files."""

    def __init__(self):
        endpoint = os.getenv("S3_ENDPOINT")
        region = os.getenv("S3_REGION")
        access_key = os.getenv("S3_ACCESS_KEY")
        secret_key = os.getenv("S3_SECRET_KEY")
        bucket = os.getenv("S3_BUCKET")

        if not (endpoint and region and access_key and secret_key and bucket):
            raise RuntimeError("Missing S3 env vars")

        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.endpoint = endpoint.rstrip("/")
        self._s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        try:
            # HeadBucket: если bucket есть — ок.
            self._s3.head_bucket(Bucket=self.bucket)
        except Exception:
            # При первом старте MinIO bucket может отсутствовать.
            self._s3.create_bucket(Bucket=self.bucket)

    def key_for_task(self, client_id: str, task_id: str) -> str:
        """stage4/tasks/<clientId>/<taskId>.wav"""
        safe_client = str(client_id).strip()
        safe_task = str(task_id).strip()
        return f"stage4/tasks/{safe_client}/{safe_task}.wav"

    def upload_file(self, *, key: str, file_path: Path) -> None:
        self._s3.upload_file(
            str(file_path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": "audio/wav"},
        )


def maybe_get_s3_storage() -> S3ObjectStorage | None:
    """Если S3 env не заданы — возвращаем None."""
    try:
        # Минимальный признак: S3_ENDPOINT и S3_BUCKET
        if not (os.getenv("S3_ENDPOINT") and os.getenv("S3_BUCKET")):
            return None
        return S3ObjectStorage()
    except Exception:
        return None
