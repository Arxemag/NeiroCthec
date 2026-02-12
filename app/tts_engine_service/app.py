from __future__ import annotations

import math
import os
import struct
import tempfile
import wave
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

app = FastAPI(title="Standalone TTS Engine")


class EmotionPayload(BaseModel):
    energy: float = 1.0
    tempo: float = 1.0
    pitch: float = 0.0


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    speaker: str = "narrator"
    emotion: EmotionPayload = Field(default_factory=EmotionPayload)


_BACKEND = os.getenv("TTS_BACKEND", "coqui").strip().lower()  # coqui | mock | auto
_COQUI = None
_COQUI_ERROR: str | None = None

if _BACKEND in {"coqui", "auto"}:
    try:
        from TTS.api import TTS  # type: ignore

        model_name = os.getenv("TTS_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
        use_gpu = os.getenv("TTS_USE_GPU", "false").lower() == "true"
        _COQUI = TTS(model_name=model_name, progress_bar=False, gpu=use_gpu)
    except Exception as exc:  # backend init diagnostics
        _COQUI_ERROR = str(exc)


def _speaker_sample_for(speaker: str) -> str | None:
    voices_root = Path(os.getenv("TTS_VOICES_ROOT", "storage/voices"))
    mapping = {
        "narrator": voices_root / "narrator.wav",
        "male": voices_root / "male.wav",
        "female": voices_root / "female.wav",
    }
    sample = mapping.get((speaker or "").lower(), mapping["narrator"])
    return str(sample) if sample.exists() else None


def _mock_synthesize(request: SynthesizeRequest) -> Response:
    sample_rate = 22050
    text_len = max(len(request.text.strip()), 1)
    duration_sec = min(max(text_len * 0.06, 0.25), 8.0)
    samples = int(duration_sec * sample_rate)

    energy = max(0.1, min(request.emotion.energy, 2.0))
    pitch_factor = request.emotion.pitch
    speaker = request.speaker.lower()
    base_freq = 180 if speaker == "male" else 230 if speaker == "female" else 200
    freq = base_freq * (2 ** pitch_factor)

    frames = bytearray()
    fade_len = max(1, int(0.01 * sample_rate))
    for i in range(samples):
        t = i / sample_rate
        amp = 0.2 * energy * math.sin(2 * math.pi * freq * t)

        if i < fade_len:
            amp *= i / fade_len
        elif i >= samples - fade_len:
            amp *= max(0.0, (samples - i - 1) / fade_len)

        int16_sample = max(-32767, min(32767, int(amp * 32767)))
        frames.extend(struct.pack("<h", int16_sample))

    wav_buffer = BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)

    duration_ms = int(duration_sec * 1000)
    return Response(
        content=wav_buffer.getvalue(),
        media_type="audio/wav",
        headers={"x-duration-ms": str(duration_ms), "x-tts-backend": "mock"},
    )


@app.get("/health")
def health() -> dict:
    active = "coqui" if _COQUI is not None else "mock"
    return {
        "status": "ok",
        "requested_backend": _BACKEND,
        "active_backend": active,
        "coqui_ready": _COQUI is not None,
        "coqui_error": _COQUI_ERROR,
    }


@app.post("/synthesize")
def synthesize(request: SynthesizeRequest) -> Response:
    # Force mock mode explicitly
    if _BACKEND == "mock":
        return _mock_synthesize(request)

    # Coqui required mode
    if _BACKEND == "coqui" and _COQUI is None:
        raise HTTPException(status_code=503, detail=f"Coqui backend is not available: {_COQUI_ERROR}")

    # auto mode fallback to mock only when coqui unavailable
    if _COQUI is None:
        return _mock_synthesize(request)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        speaker_wav = _speaker_sample_for(request.speaker)
        kwargs = {
            "text": request.text,
            "file_path": str(tmp_path),
            "split_sentences": False,
        }
        if speaker_wav:
            kwargs["speaker_wav"] = speaker_wav
            kwargs["language"] = os.getenv("TTS_LANGUAGE", "ru")

        _COQUI.tts_to_file(**kwargs)

        content = tmp_path.read_bytes()
        with wave.open(BytesIO(content), "rb") as wf:
            duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
        return Response(
            content=content,
            media_type="audio/wav",
            headers={"x-duration-ms": str(duration_ms), "x-tts-backend": "coqui"},
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
