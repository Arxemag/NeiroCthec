"""
Standalone TTS Engine — движок на Coqui XTTS v2.
Порт 8021. Контракт совместим с tts_engine_service (POST /synthesize, speaker_wav_path).
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
import wave
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

# Для разрешения голосов по speaker (narrator/male/female) используем общий реестр
import sys
_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))
from core.voices import get_voice_path  # noqa: E402

# Принять лицензию Coqui неинтерактивно (до импорта TTS)
os.environ.setdefault("COQUI_TOS_AGREED", "1")

logging.basicConfig(
    level=os.getenv("TTS_XTTS_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("tts-xtts")

_XTTS_MODEL: Any = None
_XTTS_ERROR: str | None = None
_XTTS_LOADING = False
_SAMPLE_RATE = 22050


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    speaker: str = "narrator"
    emotion: dict | None = None
    audio_config: dict | None = None
    speaker_wav_path: str | None = None


def _load_xtts() -> bool:
    global _XTTS_MODEL, _XTTS_ERROR, _XTTS_LOADING
    if _XTTS_MODEL is not None:
        return True
    if _XTTS_ERROR and "failed" in (_XTTS_ERROR or "").lower():
        return False
    if _XTTS_LOADING:
        return False
    _XTTS_LOADING = True
    try:
        from TTS.api import TTS
        use_gpu = os.getenv("TTS_USE_GPU", "true").strip().lower() in ("1", "true", "yes")
        _XTTS_MODEL = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_gpu, progress_bar=False)
        _XTTS_ERROR = None
        logger.info("XTTS v2 loaded, gpu=%s", use_gpu)
        return True
    except Exception as e:
        _XTTS_ERROR = str(e)
        logger.exception("XTTS v2 load failed: %s", e)
        return False
    finally:
        _XTTS_LOADING = False


def _resolve_speaker_wav(request: SynthesizeRequest) -> str | None:
    if request.speaker_wav_path and Path(request.speaker_wav_path).exists():
        return request.speaker_wav_path
    return get_voice_path(request.speaker)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    def _load():
        _load_xtts()
    threading.Thread(target=_load, daemon=True).start()
    yield


app = FastAPI(title="TTS Engine (XTTS2)", lifespan=_lifespan)


@app.get("/health")
def health() -> dict:
    ready = _XTTS_MODEL is not None
    status = "ok" if ready else "degraded"
    return {
        "status": status,
        "xtts_ready": ready,
        "xtts_error": _XTTS_ERROR,
        "xtts_loading": _XTTS_LOADING,
    }


@app.get("/voices")
def voices() -> list[dict]:
    from core.voices import get_voice_registry
    reg = get_voice_registry()
    return [{"id": v["id"], "path": v["path"], "source": v["source"]} for v in reg]


@app.post("/synthesize")
def synthesize(request: SynthesizeRequest) -> Response:
    if not _load_xtts():
        raise HTTPException(
            status_code=503,
            detail=_XTTS_ERROR or "XTTS v2 not loaded",
        )
    speaker_wav = _resolve_speaker_wav(request)
    if not speaker_wav:
        raise HTTPException(
            status_code=400,
            detail=f"Speaker WAV not found for speaker={request.speaker!r}. Set speaker_wav_path or add WAV to storage/voices.",
        )
    lang = "ru"
    if request.audio_config and isinstance(request.audio_config.get("language"), str):
        lang = request.audio_config["language"]
    out_path = Path(tempfile.gettempdir()) / "tts_xtts_out.wav"
    try:
        _XTTS_MODEL.tts_to_file(
            text=request.text,
            file_path=str(out_path),
            speaker_wav=speaker_wav,
            language=lang,
        )
        content = out_path.read_bytes()
        with wave.open(BytesIO(content), "rb") as wf:
            duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
        return Response(
            content=content,
            media_type="audio/wav",
            headers={"x-duration-ms": str(duration_ms)},
        )
    finally:
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("TTS_ENGINE_PORT", "8021"))
    uvicorn.run(app, host="0.0.0.0", port=port)
