from __future__ import annotations

from dataclasses import dataclass
import uuid
import os

import requests

from core.models import Line


@dataclass
class Stage4ClientConfig:
    base_url: str = os.getenv("STAGE4_TTS_URL", "http://stage4-tts:8010")
    timeout_seconds: int = 120


class Stage4TTSClient:
    """Клиент Stage 1-3 -> Stage 4 (stateless)."""

    def __init__(self, config: Stage4ClientConfig | None = None):
        self.config = config or Stage4ClientConfig()

    def synthesize_line(self, user_id: str, book_id: str, line: Line, speaker: str = "narrator") -> dict:
        payload = {
            "task_id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "book_id": str(book_id),
            "line_id": int(line.id),
            "text": line.original,
            "speaker": speaker,
            "emotion": {
                "energy": float(getattr(getattr(line, "emotion", None), "energy", 1.0)),
                "tempo": float(getattr(getattr(line, "emotion", None), "tempo", 1.0)),
                "pitch": float(getattr(getattr(line, "emotion", None), "pitch", 0.0)),
                "pause_before": int(getattr(getattr(line, "emotion", None), "pause_before", 0)),
                "pause_after": int(getattr(getattr(line, "emotion", None), "pause_after", 0)),
            },
        }

        response = requests.post(
            f"{self.config.base_url}/tts",
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
