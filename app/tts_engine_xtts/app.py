"""
Standalone TTS Engine — движок на Coqui XTTS v2.
Порт 8021. Контракт совместим с tts_engine_service (POST /synthesize, speaker_wav_path).
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
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


def _gpu_runtime_status() -> tuple[bool, str | None]:
    """Проверка CUDA (NVIDIA). Для быстрого инференса модель нужно явно переносить на GPU через tts.to('cuda')."""
    try:
        import torch  # noqa: I001
        if torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:
                name = "cuda:0"
            return True, name
        return False, None
    except Exception:
        return False, None


def _device_preference() -> str:
    """TTS_USE_GPU + наличие CUDA -> cuda, иначе cpu."""
    use_gpu = os.getenv("TTS_USE_GPU", "true").strip().lower() in ("1", "true", "yes")
    cuda_ok, _ = _gpu_runtime_status()
    return "cuda" if (use_gpu and cuda_ok) else "cpu"


def _patch_torch_load_for_coqui() -> None:
    """PyTorch 2.6+: чекпоинты Coqui требуют weights_only=False."""
    try:
        import torch
    except Exception:
        return
    original_load = getattr(torch, "load", None)
    if original_load is None or getattr(original_load, "__coqui_patched__", False):
        return

    def _patched_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    _patched_load.__coqui_patched__ = True  # type: ignore[attr-defined]
    torch.load = _patched_load  # type: ignore[assignment]


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
        _patch_torch_load_for_coqui()
        from tts_engine_xtts.xtts_patch import apply_xtts_position_embeddings_patch
        apply_xtts_position_embeddings_patch()
        from TTS.api import TTS

        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        target_device = _device_preference()
        use_gpu = target_device == "cuda"
        cuda_ok, gpu_name = _gpu_runtime_status()

        # Создаём модель без устаревшего gpu=; затем явно переносим на device (как в Ready_vers — быстрый инференс на GPU).
        try:
            tts = TTS(model_name=model_name, progress_bar=False)
        except TypeError:
            tts = TTS(model_name=model_name, progress_bar=False, gpu=use_gpu)
        if hasattr(tts, "to"):
            try:
                tts.to(target_device)
            except Exception as e:
                logger.warning("tts.to(%s) failed: %s; using default device", target_device, e)

        _XTTS_MODEL = tts
        _XTTS_ERROR = None
        logger.info(
            "XTTS v2 loaded, device=%s use_gpu=%s cuda_available=%s gpu_name=%s",
            target_device, use_gpu, cuda_ok, gpu_name or "n/a",
        )
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


# Кавычки всех видов — убираем, чтобы не озвучивались
_QUOTE_CHARS = "\"\"\"'''''\u00ab\u00bb\u201e\u201c\u2018\u2033\u2032\u2033\u300c\u300d\u301f\u00b4`"

TARGET_CHUNK_CHARS = 100


def _normalize_text_for_xtts(text: str) -> str:
    """
    Нормализация текста перед XTTS: уменьшает артифакты и «озвучивание» пунктуации.
    По документации Coqui: точка в конце часто произносится как слово; тире обрабатываются неоднозначно.
    """
    if not text or not text.strip():
        return text
    t = text.strip()
    for q in _QUOTE_CHARS:
        t = t.replace(q, "")
    lines = t.split("\n")
    normalized_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            normalized_lines.append("")
            continue
        if line.endswith(".") and len(line) > 1:
            line = line[:-1] + "..."
        elif line.endswith("...") and len(line) > 3:
            line = line.rstrip(".").rstrip() + "..."
        normalized_lines.append(line)
    t = "\n".join(normalized_lines)
    while ". " in t:
        t = t.replace(". ", "... ")
    for dash in ("\u2014", "\u2013", "\u2012"):
        t = t.replace(dash, " - ")
    while "  " in t:
        t = t.replace("  ", " ")
    return t.strip() or text.strip()


def _chunk_text(text: str, target: int = TARGET_CHUNK_CHARS, min_len: int = 60, max_len: int = 140) -> list[str]:
    """Разбиение на чанки по границам слов для ровного темпа (вариант A). Один speaker_wav на все чанки."""
    if not text or not text.strip():
        return []
    t = text.strip()
    if len(t) <= max_len:
        return [t]
    words = t.split()
    if not words:
        return [t]
    chunks = []
    current = []
    current_len = 0
    for w in words:
        w_len = len(w) + (1 if current else 0)
        if current_len + w_len > max_len and current:
            chunks.append(" ".join(current))
            current = [w]
            current_len = len(w)
        else:
            current.append(w)
            current_len += w_len
    if current:
        chunks.append(" ".join(current))
    return chunks


@asynccontextmanager
async def _lifespan(app: FastAPI):
    import asyncio
    # Загрузка модели в фоне; не принимать запросы, пока модель не готова
    def _load():
        _load_xtts()

    threading.Thread(target=_load, daemon=True).start()
    logger.info("tts-xtts: waiting for model to load (up to 300s)...")
    for i in range(300):
        await asyncio.sleep(1.0)
        if _XTTS_MODEL is not None:
            logger.info("tts-xtts: model ready, accepting requests")
            break
        if _XTTS_ERROR and "failed" in (_XTTS_ERROR or "").lower():
            logger.warning("tts-xtts: model load failed, starting anyway: %s", _XTTS_ERROR)
            break
    else:
        logger.warning("tts-xtts: model load timeout (300s), starting anyway")
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


def _xtts_inference_params(audio_config: dict | None) -> dict[str, Any]:
    """Параметры инференса из audio_config или переменных окружения."""
    cfg = audio_config or {}
    def _num(key: str, env_name: str, default: float, min_v: float, max_v: float) -> float:
        v = cfg.get(key)
        try:
            if v is not None:
                x = float(v)
            else:
                x = float(os.getenv(env_name, str(default)))
        except (TypeError, ValueError):
            x = default
        return max(min_v, min(max_v, x))

    def _int_opt(key: str, env_name: str) -> int | None:
        v = cfg.get(key)
        if v is None:
            v = os.getenv(env_name)
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _bool(key: str, env_name: str, default: bool) -> bool:
        v = cfg.get(key)
        if v is None:
            v = os.getenv(env_name)
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("1", "true", "yes", "on"):
                return True
            if s in ("0", "false", "no", "off"):
                return False
        return default

    temperature = _num("temperature", "TTS_XTTS_TEMPERATURE", 0.35, 0.05, 2.0)
    speed = _num("speed", "TTS_XTTS_SPEED", 1.0, 0.5, 2.0)
    length_penalty = _num("length_penalty", "TTS_XTTS_LENGTH_PENALTY", 1.0, 0.1, 5.0)
    repetition_penalty = _num("repetition_penalty", "TTS_XTTS_REPETITION_PENALTY", 2.0, 1.0, 5.0)
    top_k = _int_opt("top_k", "TTS_XTTS_TOP_K")
    top_p = _num("top_p", "TTS_XTTS_TOP_P", 0.85, 0.1, 1.0)
    split_sentences = _bool("split_sentences", "TTS_XTTS_SPLIT_SENTENCES", True)

    return {
        "temperature": temperature,
        "speed": speed,
        "length_penalty": length_penalty,
        "repetition_penalty": repetition_penalty,
        "top_k": top_k,
        "top_p": top_p,
        "split_sentences": split_sentences,
    }


def _concat_wavs(wav_paths: list[Path], out_path: Path) -> tuple[int, int]:
    """Склеивает WAV-файлы с одинаковыми параметрами. Возвращает (nframes, framerate)."""
    if not wav_paths:
        raise ValueError("No WAV files to concatenate")
    params = None
    all_frames: list[bytes] = []
    total_nframes = 0
    for p in wav_paths:
        with wave.open(str(p), "rb") as wf:
            p_nch, p_sw, p_fr, p_nf, p_comp, p_compn = wf.getparams()
            if params is None:
                params = (p_nch, p_sw, p_fr)
            elif (p_nch, p_sw, p_fr) != params:
                logger.warning("WAV params differ %s vs %s", (p_nch, p_sw, p_fr), params)
            all_frames.append(wf.readframes(p_nf))
            total_nframes += p_nf
    with wave.open(str(out_path), "wb") as out:
        out.setnchannels(params[0])
        out.setsampwidth(params[1])
        out.setframerate(params[2])
        for f in all_frames:
            out.writeframes(f)
    return total_nframes, params[2]


@app.post("/synthesize")
def synthesize(request: SynthesizeRequest) -> Response:
    t0 = time.perf_counter()
    logger.info("synthesize request: text_len=%s speaker=%s", len(request.text or ""), request.speaker)
    if not _load_xtts():
        raise HTTPException(
            status_code=503,
            detail=_XTTS_ERROR or "XTTS v2 not loaded",
        )
    t_load = time.perf_counter() - t0
    if t_load > 0.5:
        logger.info("xtts model ready (load/init took %.1fs)", t_load)
    logger.info("resolving speaker wav for speaker=%s", request.speaker)
    speaker_wav = _resolve_speaker_wav(request)
    logger.info("speaker wav resolved: %s", speaker_wav or "(none)")
    if not speaker_wav:
        raise HTTPException(
            status_code=400,
            detail=f"Speaker WAV not found for speaker={request.speaker!r}. Set speaker_wav_path or add WAV to storage/voices.",
        )
    lang = "ru"
    if request.audio_config and isinstance(request.audio_config.get("language"), str):
        lang = request.audio_config["language"]
    # Управление нормализацией текста только через env (не конфигурируем с фронта)
    use_normalize = os.getenv("TTS_XTTS_NORMALIZE_TEXT", "").strip().lower() in ("1", "true", "yes")
    text_clean = _normalize_text_for_xtts(request.text) if use_normalize else (request.text or "").strip()
    if not text_clean:
        raise HTTPException(status_code=400, detail="Text is empty")
    params = _xtts_inference_params(request.audio_config)
    out_path = Path(tempfile.gettempdir()) / "tts_xtts_out.wav"
    try:
        kwargs: dict[str, Any] = {
            "text": text_clean,
            "file_path": str(out_path),
            "speaker_wav": speaker_wav,
            "language": lang,
            "split_sentences": params["split_sentences"],
            "temperature": params["temperature"],
            "speed": params["speed"],
            "length_penalty": params["length_penalty"],
            "repetition_penalty": params["repetition_penalty"],
            "top_p": params["top_p"],
        }
        if params.get("top_k") is not None:
            kwargs["top_k"] = params["top_k"]
        try:
            _XTTS_MODEL.tts_to_file(**kwargs)
        except TypeError:
            kwargs.pop("temperature", None)
            kwargs.pop("speed", None)
            _XTTS_MODEL.tts_to_file(**kwargs)
        except Exception as e:
            logger.exception("tts_to_file failed: %s", e)
            raise HTTPException(status_code=500, detail=f"TTS failed: {e!s}") from e
        if not out_path.exists():
            raise HTTPException(status_code=500, detail="No audio generated")
        content = out_path.read_bytes()
        with wave.open(BytesIO(content), "rb") as wf:
            duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
        total_s = time.perf_counter() - t0
        logger.info("synthesize done in %.1fs (audio %sms)", total_s, duration_ms)
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
