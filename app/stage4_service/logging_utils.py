import json
import logging
from datetime import datetime, timezone


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


class Stage4LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": kwargs.pop("level", "INFO"),
            "task_id": self.extra.get("task_id"),
            "user_id": self.extra.get("user_id"),
            "book_id": self.extra.get("book_id"),
            "line_id": self.extra.get("line_id"),
            "stage": 4,
            "message": msg,
        }
        return json.dumps(payload, ensure_ascii=False), kwargs


def get_stage4_logger(task_id: str, user_id: str, book_id: str, line_id: int) -> Stage4LoggerAdapter:
    base_logger = logging.getLogger("stage4")
    return Stage4LoggerAdapter(
        base_logger,
        {
            "task_id": task_id,
            "user_id": user_id,
            "book_id": book_id,
            "line_id": line_id,
        },
    )
