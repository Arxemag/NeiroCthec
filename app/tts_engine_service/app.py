"""
Standalone TTS Engine — качественный движок синтеза речи.

Поддержка AMD (ROCm) и NVIDIA (CUDA), стабильная работа, возможность замены спикеров.
"""
from __future__ import annotations

import builtins
import logging
import math
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from io import BytesIO
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Загрузка Coqui в фоне — сервер сразу принимает соединения."""
    def _load():
        _init_coqui()

    th = threading.Thread(target=_load, daemon=True)
    th.start()
    yield


app = FastAPI(title="Standalone TTS Engine", lifespan=_lifespan)
logging.basicConfig(
    level=os.getenv("TTS_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("tts-engine")
logging.getLogger("matplotlib").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Environment & Coqui preparation
# ---------------------------------------------------------------------------


def _coqui_tos_auto_accept() -> bool:
    return os.getenv("TTS_COQUI_TOS_ACCEPTED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _prepare_coqui_env() -> None:
    if _coqui_tos_auto_accept():
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        os.environ.setdefault("TTS_HOME", os.getenv("TTS_HOME", "/srv/storage/tts_cache"))


def _patch_torch_load_for_coqui() -> None:
    """PyTorch 2.6+ compatibility: Coqui checkpoints require weights_only=False."""
    try:
        import torch  # type: ignore
    except Exception:
        return

    original_load = getattr(torch, "load", None)
    if original_load is None or getattr(torch.load, "__coqui_patched__", False):
        return

    def _patched_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    _patched_load.__coqui_patched__ = True  # type: ignore[attr-defined]
    torch.load = _patched_load  # type: ignore[assignment]


def _require_gpu() -> bool:
    return os.getenv("TTS_REQUIRE_GPU", "false").strip().lower() in {"1", "true", "yes", "on"}


def _gpu_runtime_status() -> tuple[bool, str | None]:
    """Detect GPU: works with both NVIDIA (CUDA) and AMD (ROCm). ROCm exposes torch.cuda API."""
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:
                name = "cuda:0"
            return True, name
        if hasattr(torch, "hip") and getattr(torch.hip, "is_available", lambda: False)():
            return True, "ROCm: AMD GPU"
        return False, None
    except Exception:
        return False, None


def _gpu_vendor() -> str | None:
    """Infer GPU vendor from device name: 'amd' | 'nvidia' | None."""
    ok, name = _gpu_runtime_status()
    if not ok or not name:
        return None
    n = name.upper()
    if "AMD" in n or "RADEON" in n:
        return "amd"
    if "NVIDIA" in n or "GEFORCE" in n or "QUADRO" in n or "TESLA" in n:
        return "nvidia"
    return None


def _device_preference() -> str:
    """
    TTS_DEVICE: auto | cuda | cpu
    auto = cuda if TTS_USE_GPU and available, else cpu
    """
    env = os.getenv("TTS_DEVICE", "auto").strip().lower()
    if env in ("cuda", "gpu"):
        return "cuda"
    if env == "cpu":
        return "cpu"
    use_gpu = os.getenv("TTS_USE_GPU", "false").strip().lower() in {"1", "true", "yes", "on"}
    cuda_ok, _ = _gpu_runtime_status()
    return "cuda" if (use_gpu and cuda_ok) else "cpu"


def _coqui_gpu_fallback_to_cpu() -> bool:
    return os.getenv("TTS_COQUI_GPU_FALLBACK_CPU", "true").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EmotionPayload(BaseModel):
    energy: float = 1.0
    tempo: float = 1.0
    pitch: float = 0.0


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    speaker: str = "narrator"
    emotion: EmotionPayload = Field(default_factory=EmotionPayload)
    language: str | None = None
    voice_sample: str | None = None
    audio_config: dict | None = None


class VoiceInfo(BaseModel):
    id: str
    path: str
    source: str  # builtin | config | discovered


# ---------------------------------------------------------------------------
# Coqui initialization
# ---------------------------------------------------------------------------

_BACKEND = os.getenv("TTS_BACKEND", "auto").strip().lower()
_COQUI: Any = None
_COQUI_ERROR: str | None = None
_COQUI_ACTIVE_DEVICE: str | None = None
_COQUI_MODEL_NAME = os.getenv("TTS_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")


def _build_tts_instance(TTS_cls: Any, model_name: str, use_gpu: bool) -> Any:
    original_input = builtins.input

    def _auto_input(prompt: str = "") -> str:
        if _coqui_tos_auto_accept():
            return "y"
        return original_input(prompt)

    try:
        builtins.input = _auto_input
        try:
            tts = TTS_cls(model_name=model_name, progress_bar=False)
        except TypeError:
            tts = TTS_cls(model_name=model_name, progress_bar=False, gpu=use_gpu)

        target_device = "cuda" if use_gpu else "cpu"
        if hasattr(tts, "to"):
            try:
                tts.to(target_device)
            except Exception as e:
                logger.warning("tts.to(%s) failed: %s; using default device", target_device, e)
        return tts
    finally:
        builtins.input = original_input


def _init_coqui() -> None:
    global _COQUI, _COQUI_ERROR, _COQUI_ACTIVE_DEVICE
    if _BACKEND not in {"coqui", "auto"}:
        return

    _prepare_coqui_env()
    _patch_torch_load_for_coqui()
    logger.info("Coqui env: COQUI_TOS_AGREED=%s TTS_HOME=%s", os.getenv("COQUI_TOS_AGREED"), os.getenv("TTS_HOME"))

    try:
        from TTS.api import TTS  # type: ignore
    except Exception as exc:
        _COQUI = None
        _COQUI_ERROR = f"Failed to import TTS.api: {exc}"
        _COQUI_ACTIVE_DEVICE = None
        logger.exception("Coqui import failed")
        return

    use_gpu = _device_preference() == "cuda"
    try:
        _COQUI = _build_tts_instance(TTS, _COQUI_MODEL_NAME, use_gpu)
        _COQUI_ERROR = None
        _COQUI_ACTIVE_DEVICE = "cuda" if use_gpu else "cpu"
        logger.info("Coqui init OK: model=%s device=%s", _COQUI_MODEL_NAME, _COQUI_ACTIVE_DEVICE)
        return
    except Exception as exc:
        _COQUI = None
        _COQUI_ERROR = str(exc)
        _COQUI_ACTIVE_DEVICE = None
        logger.exception("Coqui init failed with gpu=%s", use_gpu)

    if use_gpu and _coqui_gpu_fallback_to_cpu():
        try:
            _COQUI = _build_tts_instance(TTS, _COQUI_MODEL_NAME, False)
            _COQUI_ERROR = None
            _COQUI_ACTIVE_DEVICE = "cpu"
            logger.warning("Coqui fallback to CPU after GPU init failure")
        except Exception as exc:
            _COQUI = None
            _COQUI_ERROR = f"GPU and CPU fallback failed: {exc}"
            logger.exception("Coqui CPU fallback failed")


# Coqui загружается в фоне при старте (lifespan)
_ESPEAK_BIN = shutil.which("espeak") or shutil.which("espeak-ng")


# ---------------------------------------------------------------------------
# Speaker registry — замена и расширение спикеров
# ---------------------------------------------------------------------------


def _voices_root() -> Path:
    return Path(os.getenv("TTS_VOICES_ROOT", "storage/voices"))


def _shared_storage_root() -> Path:
    return Path(os.getenv("SHARED_STORAGE_ROOT", "/srv/storage"))


def _load_raw_config() -> dict:
    """Load raw voices config (voices + aliases) from YAML/JSON."""
    root = _voices_root()
    shared = _shared_storage_root()
    candidates = [
        root / "voices.yaml",
        root / "voices.yml",
        root / "voices.json",
        shared / "voices" / "voices.yaml",
        shared / "voices" / "voices.yml",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(content)
            else:
                import json
                data = json.loads(content)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning("Failed to load voices config %s: %s", path, e)
    return {}


def _load_voices_config() -> dict[str, str]:
    """Load voices (id -> path) from voices.yaml, excluding aliases."""
    data = _load_raw_config()
    out: dict[str, str] = {}
    for k, v in data.items():
        if k.strip().lower() == "aliases":
            continue
        if isinstance(k, str) and isinstance(v, str) and v.strip():
            out[k.strip().lower()] = v.strip()
    return out


def _load_speaker_aliases() -> dict[str, str]:
    """Load alias -> main_speaker from voices.yaml aliases. Builtin fallback."""
    builtin: dict[str, str] = {
        "famaly": "female", "femaly": "female", "woman": "female", "girl": "female",
        "man": "male", "boy": "male",
        "main": "narrator", "default": "narrator", "storyteller": "narrator", "narr": "narrator",
    }
    data = _load_raw_config()
    aliases_cfg = data.get("aliases") if isinstance(data.get("aliases"), dict) else {}
    for main_speaker, alias_list in aliases_cfg.items():
        if not isinstance(main_speaker, str) or not main_speaker.strip():
            continue
        main = main_speaker.strip().lower()
        for a in (alias_list if isinstance(alias_list, (list, tuple)) else []):
            if isinstance(a, str) and a.strip():
                builtin[a.strip().lower()] = main
    return builtin


def _resolve_voices_root_path(raw: str) -> Path:
    """Resolve path relative to shared storage or voices root."""
    raw = raw.strip()
    if not raw:
        return Path()
    p = Path(raw)
    if p.is_absolute():
        return p
    shared = _shared_storage_root()
    root = _voices_root()
    if raw.startswith("storage/"):
        return shared / raw[len("storage/"):]
    if raw.startswith("voices/"):
        return shared / "storage" / raw
    return root / raw


def _discover_voices_from_dir() -> dict[str, str]:
    """Discover .wav files in TTS_VOICES_ROOT; filename (without ext) = speaker id."""
    root = _voices_root()
    shared_voices = _shared_storage_root() / "voices"
    result: dict[str, str] = {}
    for base in (root, shared_voices):
        if not base.exists():
            continue
        for f in base.glob("*.wav"):
            sid = f.stem.lower()
            if sid and sid not in result:
                result[sid] = str(f.resolve())
    return result


def _builtin_voice_mapping() -> dict[str, str]:
    root = _voices_root()
    shared = _shared_storage_root() / "voices"
    mapping = {
        "narrator": "narrator.wav",
        "male": "male.wav",
        "female": "female.wav",
    }
    result: dict[str, str] = {}
    for sid, fn in mapping.items():
        for base in (root, shared):
            p = base / fn
            if p.exists():
                result[sid] = str(p.resolve())
                break
    return result


def _get_speaker_registry() -> dict[str, tuple[str, str]]:
    """
    Merged registry: { speaker_id -> (resolved_path, source) }.
    Priority: config file > discovered > builtin.
    """
    registry: dict[str, tuple[str, str]] = {}

    builtin = _builtin_voice_mapping()
    for sid, path in builtin.items():
        registry[sid] = (path, "builtin")

    discovered = _discover_voices_from_dir()
    for sid, path in discovered.items():
        registry[sid] = (path, "discovered")  # overwrites builtin if same id

    config = _load_voices_config()
    for sid, raw_path in config.items():
        resolved = _resolve_voices_root_path(raw_path)
        if resolved.exists():
            registry[sid] = (str(resolved.resolve()), "config")
        else:
            abs_candidates = [Path(raw_path), _voices_root() / raw_path, _shared_storage_root() / raw_path]
            for c in abs_candidates:
                if c.exists():
                    registry[sid] = (str(c.resolve()), "config")
                    break

    return registry


def _list_available_voices() -> list[VoiceInfo]:
    reg = _get_speaker_registry()
    return [VoiceInfo(id=sid, path=path, source=src) for sid, (path, src) in sorted(reg.items())]


def _normalize_speaker_label(speaker: str | None) -> str:
    raw = (speaker or "").strip().lower()
    aliases = _load_speaker_aliases()
    return aliases.get(raw, raw)


def _resolve_shared_voice_sample_path(path_value: str | None) -> str | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    raw = path_value.strip()
    p = Path(raw)
    candidates: list[Path] = []

    if p.is_absolute():
        candidates.append(p)
    else:
        cwd = Path.cwd()
        candidates.append(cwd / p)
        shared = _shared_storage_root()
        if raw.startswith("storage/"):
            candidates.append(shared / raw[len("storage/"):])
        candidates.append(_voices_root() / raw)

    for c in candidates:
        if c.exists():
            return str(c.resolve())
    return None


def _speaker_sample_for(speaker: str) -> str | None:
    """Resolve speaker -> wav path using registry (supports custom speakers)."""
    sid = _normalize_speaker_label(speaker)
    reg = _get_speaker_registry()

    if sid in reg:
        return reg[sid][0]
    if "narrator" in reg:
        return reg["narrator"][0]
    return None


def _resolve_coqui_speaker_wav(request: SynthesizeRequest) -> str | None:
    resolved = _resolve_shared_voice_sample_path(request.voice_sample)
    if resolved:
        return resolved

    cfg = request.audio_config or {}
    voices = cfg.get("voices") if isinstance(cfg, dict) else None
    if isinstance(voices, dict):
        speaker_key = _normalize_speaker_label(request.speaker)
        sample = voices.get(speaker_key) or voices.get("narrator")
        resolved_cfg = _resolve_shared_voice_sample_path(sample if isinstance(sample, str) else None)
        if resolved_cfg:
            return resolved_cfg

    return _speaker_sample_for(request.speaker)


# ---------------------------------------------------------------------------
# Language, XTTS params
# ---------------------------------------------------------------------------


def _resolve_coqui_language(request: SynthesizeRequest) -> str:
    if request.language and request.language.strip():
        return request.language.strip()
    cfg = request.audio_config or {}
    engine = cfg.get("engine") if isinstance(cfg, dict) else None
    if isinstance(engine, dict):
        lang = engine.get("language")
        if isinstance(lang, str) and lang.strip():
            return lang.strip()
    return os.getenv("TTS_LANGUAGE", "ru")


def _resolve_xtts_speed(request: SynthesizeRequest) -> float:
    cfg = request.audio_config or {}
    xtts = cfg.get("xtts") if isinstance(cfg, dict) else None
    speed_base = 1.0
    if isinstance(xtts, dict):
        raw = xtts.get("speed_base")
        if isinstance(raw, (int, float)):
            speed_base = float(raw)
    tempo = request.emotion.tempo if isinstance(request.emotion.tempo, (int, float)) else 1.0
    final_speed = speed_base * float(tempo)
    return max(0.5, min(final_speed, 2.0))


def _resolve_xtts_params(request: SynthesizeRequest) -> dict:
    """XTTS params with sensible defaults for stability."""
    cfg = request.audio_config or {}
    xtts = cfg.get("xtts") if isinstance(cfg, dict) else None
    xtts = xtts if isinstance(xtts, dict) else {}

    out: dict = {}

    def _num(
        name: str,
        min_v: float | None = None,
        max_v: float | None = None,
        as_int: bool = False,
        default: float | int | None = None,
    ):
        raw = xtts.get(name)
        if not isinstance(raw, (int, float)) and default is not None:
            raw = default
        if isinstance(raw, (int, float)):
            value = float(raw)
            if min_v is not None:
                value = max(min_v, value)
            if max_v is not None:
                value = min(max_v, value)
            out[name] = int(round(value)) if as_int else value

    _num("temperature", 0.05, 2.0, default=0.7)
    _num("top_k", 1, 400, as_int=True, default=50)
    _num("top_p", 0.1, 1.0, default=0.9)
    _num("repetition_penalty", 1.0, 10.0, default=2.0)
    return out


def _coqui_requires_speaker_wav() -> bool:
    return "xtts" in (_COQUI_MODEL_NAME or "").lower()


def _degraded_backend_allowed() -> bool:
    return os.getenv("TTS_ALLOW_DEGRADED_BACKEND", "false").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Synthesis backends
# ---------------------------------------------------------------------------


def _mock_synthesize(request: SynthesizeRequest) -> Response:
    sample_rate = 22050
    text_len = max(len(request.text.strip()), 1)
    duration_sec = min(max(text_len * 0.06, 0.25), 8.0)
    samples = int(duration_sec * sample_rate)

    energy = max(0.1, min(request.emotion.energy, 2.0))
    pitch_factor = request.emotion.pitch
    speaker = _normalize_speaker_label(request.speaker)
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


def _resolve_espeak_voice(request: SynthesizeRequest) -> str:
    if request.language and request.language.strip():
        return request.language.strip()
    cfg = request.audio_config or {}
    engine = cfg.get("engine") if isinstance(cfg, dict) else None
    if isinstance(engine, dict):
        lang = engine.get("language")
        if isinstance(lang, str) and lang.strip():
            return lang.strip()
    return os.getenv("ESPEAK_VOICE", "ru")


def _espeak_synthesize(request: SynthesizeRequest) -> Response:
    if not _ESPEAK_BIN:
        raise HTTPException(status_code=503, detail="espeak backend is not available")
    voice = _resolve_espeak_voice(request)
    base_speed = int(os.getenv("ESPEAK_SPEED", "165"))
    speed = max(80, min(260, int(base_speed * max(0.6, min(request.emotion.tempo, 1.6)))))

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [_ESPEAK_BIN, "-v", voice, "-s", str(speed), "-w", str(tmp_path), request.text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        content = tmp_path.read_bytes()
        with wave.open(BytesIO(content), "rb") as wf:
            duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
        return Response(
            content=content,
            media_type="audio/wav",
            headers={"x-duration-ms": str(duration_ms), "x-tts-backend": "espeak"},
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    cuda_ok, cuda_name = _gpu_runtime_status()
    gpu_vendor = _gpu_vendor()
    active = "coqui" if _COQUI is not None else "espeak" if _ESPEAK_BIN else "mock"
    return {
        "status": "ok",
        "requested_backend": _BACKEND,
        "active_backend": active,
        "coqui_ready": _COQUI is not None,
        "coqui_error": _COQUI_ERROR,
        "coqui_model_name": _COQUI_MODEL_NAME,
        "coqui_device": _COQUI_ACTIVE_DEVICE,
        "device_preference": _device_preference(),
        "cuda_available": cuda_ok,
        "cuda_device": cuda_name,
        "gpu_vendor": gpu_vendor,
        "default_language": os.getenv("TTS_LANGUAGE", "ru"),
        "voices_root": str(_voices_root()),
        "espeak_ready": _ESPEAK_BIN is not None,
        "voices_count": len(_get_speaker_registry()),
    }


@app.get("/voices", response_model=list[VoiceInfo])
def list_voices() -> list[VoiceInfo]:
    """Список доступных голосов. Можно заменять: добавить .wav в TTS_VOICES_ROOT или настроить voices.yaml."""
    return _list_available_voices()


@app.post("/synthesize")
def synthesize(request: SynthesizeRequest) -> Response:
    if _require_gpu() and not _gpu_runtime_status()[0]:
        raise HTTPException(status_code=503, detail="GPU required but not available (install CUDA or ROCm PyTorch)")

    if _BACKEND == "mock":
        return _mock_synthesize(request)
    if _BACKEND == "espeak":
        return _espeak_synthesize(request)

    if _BACKEND == "coqui":
        if _COQUI is None:
            _init_coqui()
        if _COQUI is None:
            raise HTTPException(status_code=503, detail=f"Coqui backend unavailable: {_COQUI_ERROR}")
        if _require_gpu() and _COQUI_ACTIVE_DEVICE != "cuda":
            raise HTTPException(status_code=503, detail="GPU required but Coqui is on CPU")
    elif _BACKEND == "auto":
        if _COQUI is None:
            _init_coqui()
        if _COQUI is None:
            if not _degraded_backend_allowed():
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Coqui unavailable, degraded fallback disabled. "
                        "Set TTS_ALLOW_DEGRADED_BACKEND=true for espeak/mock. "
                        f"Error: {_COQUI_ERROR}"
                    ),
                )
            if _ESPEAK_BIN:
                return _espeak_synthesize(request)
            return _mock_synthesize(request)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        speaker_wav = _resolve_coqui_speaker_wav(request)
        language = _resolve_coqui_language(request)
        logger.info("coqui: language=%s speaker=%s speaker_wav=%s", language, request.speaker, speaker_wav)

        kwargs: dict[str, Any] = {
            "text": request.text,
            "file_path": str(tmp_path),
            "split_sentences": False,
            "language": language,
        }
        if "xtts" in (_COQUI_MODEL_NAME or "").lower():
            kwargs["speed"] = _resolve_xtts_speed(request)
            kwargs.update(_resolve_xtts_params(request))
        if speaker_wav:
            kwargs["speaker_wav"] = speaker_wav
        elif _coqui_requires_speaker_wav():
            voices_list = ", ".join(v.id for v in _list_available_voices()[:8])
            raise HTTPException(
                status_code=422,
                detail=(
                    "XTTS requires a reference speaker wav. "
                    "Add .wav files to TTS_VOICES_ROOT or configure voices.yaml. "
                    f"Available: {voices_list}"
                ),
            )

        dev = _COQUI_ACTIVE_DEVICE or "cpu"
        vendor = _gpu_vendor()
        logger.info("coqui synthesize: device=%s gpu_vendor=%s gpu_name=%s", dev, vendor, _gpu_runtime_status()[1])
        _COQUI.tts_to_file(**kwargs)

        content = tmp_path.read_bytes()
        with wave.open(BytesIO(content), "rb") as wf:
            duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
        speaker_label = _normalize_speaker_label(request.speaker)
        speaker_marker = Path(speaker_wav).name if speaker_wav else "none"
        headers = {
            "x-duration-ms": str(duration_ms),
            "x-tts-backend": "coqui",
            "x-tts-language": language,
            "x-tts-speaker": speaker_label,
            "x-tts-speaker-wav": speaker_marker,
        }
        if _COQUI_ACTIVE_DEVICE:
            headers["x-tts-device"] = _COQUI_ACTIVE_DEVICE
        v = _gpu_vendor()
        if v:
            headers["x-tts-gpu-vendor"] = v
        return Response(content=content, media_type="audio/wav", headers=headers)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
