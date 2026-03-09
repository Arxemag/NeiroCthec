"""Синтезаторы для Stage4: mock (тишина) и внешний HTTP TTS."""
import base64
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

    def synthesize_batch(
        self, requests: list[TTSRequest]
    ) -> list[tuple[bytes, float]]:
        """Batch: sequential synthesize for mock."""
        import tempfile
        results = []
        for r in requests:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                path = Path(tmp.name)
            dur = self.synthesize(r, path)
            results.append((path.read_bytes(), dur))
            path.unlink(missing_ok=True)
        return results


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
        payload = {
            "text": request.text,
            "speaker": request.speaker,
            "emotion": request.emotion or {},
            "audio_config": request.audio_config or {},
        }
        if getattr(request, "speaker_wav_path", None):
            payload["speaker_wav_path"] = request.speaker_wav_path
        url = f"{self.base_url}/synthesize"
        import logging
        log = logging.getLogger(__name__)
        log.info("External TTS request: POST %s book_id=%s line_id=%s", url, getattr(request, "book_id", ""), getattr(request, "line_id", ""))
        max_retries = 2  # при ReadTimeout повторить (первый запрос может грузить модель)
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                resp = self._requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                output_path.write_bytes(resp.content)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries and ("timed out" in str(exc).lower() or "read timeout" in str(exc).lower()):
                    log.warning("TTS request timed out, retry %s/%s", attempt + 1, max_retries)
                    continue
                raise
        else:
            if last_exc is not None:
                raise last_exc
        # Примерная длительность по размеру: 16-bit mono 22kHz ≈ 44k bytes/sec
        size = output_path.stat().st_size
        duration_sec = size / (22050 * 2)
        return duration_sec * 1000.0

    def synthesize_batch(
        self, requests: list[TTSRequest]
    ) -> list[tuple[bytes, float]]:
        """Batch synthesis: one HTTP request, returns [(audio_bytes, duration_ms), ...]."""
        if not requests:
            return []
        items = []
        for r in requests:
            item = {
                "text": r.text,
                "speaker": r.speaker,
                "emotion": r.emotion or {},
                "audio_config": r.audio_config or {},
            }
            if getattr(r, "speaker_wav_path", None):
                item["speaker_wav_path"] = r.speaker_wav_path
            items.append(item)
        resp = self._requests.post(
            f"{self.base_url}/synthesize-batch",
            json={"items": items},
            timeout=self.timeout * max(1, len(requests)),
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("results", []):
            content = base64.b64decode(r.get("content_base64", ""))
            duration_ms = float(r.get("duration_ms", 0))
            results.append((content, duration_ms))
        return results
