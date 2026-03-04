"""Синтезаторы для Stage4: mock (тишина) и внешний HTTP TTS."""
from pathlib import Path

from stage4_service.schemas import TTSRequest, TTSResponse, TTSStatus


class MockSynthesizer:
    """Генерирует короткий WAV с тишиной (для проверки пайплайна без реального TTS)."""

    def synthesize(self, request: TTSRequest, output_path: Path) -> float:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # 0.3 сек тишины, 22050 Hz, моно 16-bit
        import wave
        import struct
        sr = 22050
        duration_sec = 0.3
        with wave.open(str(output_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sr)
            frames = int(sr * duration_sec)
            wav.writeframes(struct.pack("<h", 0) * frames)
        return duration_sec * 1000.0


class ExternalHTTPSynthesizer:
    """Вызывает внешний TTS по HTTP (например tts_engine_service)."""

    def __init__(self, base_url: str, timeout_sec: int = 60):
        import requests
        self._requests = requests
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_sec

    def synthesize(self, request: TTSRequest, output_path: Path) -> float:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        resp = self._requests.post(
            f"{self.base_url}/synthesize",
            json={
                "text": request.text,
                "speaker": request.speaker,
                "emotion": request.emotion or {},
                "audio_config": request.audio_config or {},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        # Примерная длительность по размеру: 16-bit mono 22kHz ≈ 44k bytes/sec
        size = output_path.stat().st_size
        duration_sec = size / (22050 * 2)
        return duration_sec * 1000.0
