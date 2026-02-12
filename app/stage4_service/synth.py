from pathlib import Path
import math
import struct
import wave
from abc import ABC, abstractmethod

import requests

from stage4_service.schemas import TTSRequest


class BaseSynthesizer(ABC):
    @abstractmethod
    def synthesize(self, request: TTSRequest, output_path: Path) -> int:
        """Synthesize speech and store audio into output_path, returning duration_ms."""


class MockSynthesizer(BaseSynthesizer):
    """MVP-синтезатор: генерирует простой сигнал и сохраняет WAV (без внешних audio libs)."""

    sample_rate = 22050

    def synthesize(self, request: TTSRequest, output_path: Path) -> int:
        text_len = max(len(request.text.strip()), 1)
        duration_sec = min(max(text_len * 0.06, 0.25), 8.0)
        samples = int(duration_sec * self.sample_rate)

        energy = max(0.1, min(request.emotion.energy, 2.0))
        pitch_factor = request.emotion.pitch
        speaker = request.speaker.lower()
        base_freq = 180 if speaker == "male" else 230 if speaker == "female" else 200
        freq = base_freq * (2 ** pitch_factor)

        fade_len = max(1, int(0.01 * self.sample_rate))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # int16
            wav_file.setframerate(self.sample_rate)

            frames = bytearray()
            for i in range(samples):
                t = i / self.sample_rate
                amp = 0.2 * energy * math.sin(2 * math.pi * freq * t)

                if i < fade_len:
                    amp *= i / fade_len
                elif i >= samples - fade_len:
                    amp *= max(0.0, (samples - i - 1) / fade_len)

                int16_sample = max(-32767, min(32767, int(amp * 32767)))
                frames.extend(struct.pack("<h", int16_sample))

            wav_file.writeframes(frames)

        return int(duration_sec * 1000)


class ExternalHTTPSynthesizer(BaseSynthesizer):
    @staticmethod
    def _resolve_language(request: TTSRequest) -> str | None:
        if request.language:
            return request.language
        cfg = request.audio_config or {}
        engine = cfg.get("engine") if isinstance(cfg, dict) else None
        if isinstance(engine, dict):
            lang = engine.get("language")
            if isinstance(lang, str) and lang.strip():
                return lang.strip()
        return None

    @staticmethod
    def _resolve_voice_sample(request: TTSRequest) -> str | None:
        cfg = request.audio_config or {}
        voices = cfg.get("voices") if isinstance(cfg, dict) else None
        if isinstance(voices, dict):
            sample = voices.get((request.speaker or "").lower()) or voices.get("narrator")
            if isinstance(sample, str) and sample.strip():
                return sample.strip()
        return None

    """Adapter for standalone TTS service with HTTP API."""

    def __init__(self, base_url: str, timeout_sec: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def synthesize(self, request: TTSRequest, output_path: Path) -> int:
        response = requests.post(
            f"{self.base_url}/synthesize",
            json={
                "text": request.text,
                "speaker": request.speaker,
                "emotion": request.emotion.model_dump(),
                "language": self._resolve_language(request),
                "voice_sample": self._resolve_voice_sample(request),
                "audio_config": request.audio_config,
            },
            timeout=self.timeout_sec,
        )
        response.raise_for_status()

        duration_ms = int(response.headers.get("x-duration-ms", "0") or "0")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return duration_ms
