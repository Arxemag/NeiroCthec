"""
Standalone TTS Engine — движок синтеза речи на Qwen3-TTS.

Поддержка русского языка, AMD (ROCm) и NVIDIA (CUDA).
"""
from __future__ import annotations

import base64
from collections import defaultdict
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
    """Загрузка Base 4-bit модели в фоне — сервер сразу принимает соединения."""
    global _QWEN3_BASE_LOADING
    _QWEN3_BASE_LOADING = True

    def _load():
        global _QWEN3_BASE_LOADING
        try:
            _init_qwen3_base()
            if _QWEN3_BASE is not None:
                logger.info("Qwen3-TTS Base загружена, устройство: %s", _QWEN3_BASE_DEVICE)
            elif _QWEN3_BASE_ERROR:
                logger.error("Qwen3-TTS Base не загружена: %s. Проверьте GET /health для деталей.", _QWEN3_BASE_ERROR)
        except Exception as e:
            logger.exception("Ошибка при загрузке Qwen3-TTS в фоне: %s", e)
        finally:
            _QWEN3_BASE_LOADING = False

    th = threading.Thread(target=_load, daemon=True)
    th.start()
    yield


app = FastAPI(title="Standalone TTS Engine (Qwen3)", lifespan=_lifespan)
logging.basicConfig(
    level=os.getenv("TTS_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("tts-engine")
logging.getLogger("matplotlib").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Environment & GPU (CUDA / ROCm)
# ---------------------------------------------------------------------------

_BACKEND = os.getenv("TTS_BACKEND", "qwen3").strip().lower()
# Единственная модель — Base 4-bit для клонирования голоса по WAV
_QWEN3_BASE: Any = None
_QWEN3_BASE_ERROR: str | None = None
_QWEN3_BASE_LOADING: bool = False
_QWEN3_BASE_MODEL_NAME = os.getenv("TTS_QWEN3_BASE_MODEL", "divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit")
_QWEN3_BASE_DEVICE: str | None = None  # "cuda" or "cpu" after load

# Кэш voice_clone_prompt по пути к WAV — не пересчитываем фичи при каждом запросе
_VOICE_CLONE_PROMPT_CACHE: dict[str, Any] = {}
_VOICE_CLONE_CACHE_LOCK = threading.Lock()
_VOICE_CLONE_CACHE_MAX = int(os.getenv("TTS_VOICE_CLONE_CACHE_MAX", "16"))

# Отладка: каталог и счётчик для записи текста, передаваемого в TTS
_DEBUG_TTS_DIR = Path(__file__).resolve().parent.parent / "storage" / "debug" / "text-to-tts"
_DEBUG_TTS_INDEX = 0
_DEBUG_TTS_LOCK = threading.Lock()


def _debug_log_text_to_tts(request: "SynthesizeRequest") -> None:
    """Пишет переданный в TTS текст в storage/debug/text-to-tts с индексом попытки."""
    global _DEBUG_TTS_INDEX
    try:
        with _DEBUG_TTS_LOCK:
            _DEBUG_TTS_INDEX += 1
            idx = _DEBUG_TTS_INDEX
        _DEBUG_TTS_DIR.mkdir(parents=True, exist_ok=True)
        base = _DEBUG_TTS_DIR / f"{idx:06d}"
        base.with_suffix(".txt").write_text(request.text or "", encoding="utf-8")
        meta_lines = [
            f"attempt={idx}",
            f"speaker={getattr(request, 'speaker', '') or ''}",
            f"voice_description={getattr(request, 'voice_description', '') or ''}",
            f"language={getattr(request, 'language', '') or ''}",
        ]
        base.with_suffix(".meta").write_text("\n".join(meta_lines), encoding="utf-8")
        logger.debug("TTS debug: wrote text attempt %s to %s", idx, base.with_suffix(".txt"))
    except Exception as e:
        logger.warning("TTS debug write failed: %s", e)


def _require_gpu() -> bool:
    return os.getenv("TTS_REQUIRE_GPU", "false").strip().lower() in {"1", "true", "yes", "on"}


def _gpu_runtime_status() -> tuple[bool, str | None]:
    """Detect GPU: NVIDIA (CUDA) and AMD (ROCm). ROCm exposes torch.cuda API."""
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
    """Infer GPU vendor: 'amd' | 'nvidia' | None."""
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
    TTS_DEVICE: auto | cuda | cpu.
    - auto: использовать GPU (CUDA/ROCm), если доступен; иначе CPU.
      TTS_USE_GPU=false принудительно выбирает CPU при auto.
    - cuda | gpu: принудительно GPU.
    - cpu: принудительно CPU.
    Для AMD GPU нужен PyTorch с ROCm (Linux или Windows по инструкции AMD).
    """
    env = os.getenv("TTS_DEVICE", "auto").strip().lower()
    if env in ("cuda", "gpu"):
        return "cuda"
    if env == "cpu":
        return "cpu"
    cuda_ok, cuda_name = _gpu_runtime_status()
    force_no_gpu = os.getenv("TTS_USE_GPU", "").strip().lower() in {"0", "false", "no", "off"}
    if force_no_gpu:
        return "cpu"
    return "cuda" if cuda_ok else "cpu"


def _qwen3_gpu_fallback_to_cpu() -> bool:
    return os.getenv("TTS_QWEN3_GPU_FALLBACK_CPU", "true").strip().lower() in {"1", "true", "yes", "on"}


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
    """Текстовое описание голоса для VoiceDesign, например: «низкий мужской голос, спокойный»."""
    voice_description: str | None = None
    """Готовый путь к WAV образца голоса (для XTTS2 и voice clone). Имеет приоритет над speaker/voice_ids."""
    speaker_wav_path: str | None = None


class VoiceInfo(BaseModel):
    id: str
    path: str
    source: str  # builtin | config | discovered


class SynthesizeBatchItem(BaseModel):
    text: str = Field(min_length=1)
    speaker: str = "narrator"
    emotion: EmotionPayload | None = None
    language: str | None = None
    voice_sample: str | None = None
    audio_config: dict | None = None
    speaker_wav_path: str | None = None


class SynthesizeBatchRequest(BaseModel):
    items: list[SynthesizeBatchItem] = Field(min_length=1, max_length=16)


class SynthesizeBatchResult(BaseModel):
    content_base64: str
    duration_ms: int


class SynthesizeBatchResponse(BaseModel):
    results: list[SynthesizeBatchResult]


# ---------------------------------------------------------------------------
# Qwen3-TTS Base 4-bit (единственная модель — voice clone по WAV)
# ---------------------------------------------------------------------------


def _init_qwen3_base() -> bool:
    """Загрузка Base 4-bit модели для клонирования голоса по WAV (storage/voices или voice_sample)."""
    global _QWEN3_BASE, _QWEN3_BASE_ERROR, _QWEN3_BASE_DEVICE
    if _QWEN3_BASE is not None:
        return True
    if _QWEN3_BASE_ERROR is not None and "failed" in _QWEN3_BASE_ERROR.lower():
        return False
    try:
        import torch  # type: ignore
        from qwen_tts import Qwen3TTSModel  # type: ignore
    except Exception as exc:
        _QWEN3_BASE_ERROR = str(exc)
        return False
    use_gpu = _device_preference() == "cuda"
    device_map = "auto" if use_gpu else "cpu"
    dtype = getattr(torch, "bfloat16", torch.float16)
    try:
        _QWEN3_BASE = Qwen3TTSModel.from_pretrained(
            _QWEN3_BASE_MODEL_NAME,
            device_map=device_map,
            dtype=dtype,
            attn_implementation="sdpa",
        )
        if hasattr(torch, "compile") and os.getenv("TTS_TORCH_COMPILE", "false").lower() in ("1", "true", "yes"):
            try:
                _QWEN3_BASE = torch.compile(_QWEN3_BASE, mode="reduce-overhead")
                logger.info("Qwen3-TTS Base torch.compile enabled")
            except Exception as compile_exc:
                logger.warning("torch.compile skipped for Base model: %s", compile_exc)
        _QWEN3_BASE_ERROR = None
        _QWEN3_BASE_DEVICE = "cuda" if use_gpu else "cpu"
        logger.info("Qwen3-TTS Base (voice clone) loaded: %s on %s", _QWEN3_BASE_MODEL_NAME, device_map)
        return True
    except Exception as exc:
        _QWEN3_BASE_ERROR = str(exc)
        logger.exception("Qwen3-TTS Base load failed")
        return False


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
    if request.speaker_wav_path and Path(request.speaker_wav_path).exists():
        return request.speaker_wav_path
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


def _resolve_language(request: SynthesizeRequest) -> str:
    """Язык для Qwen3: Russian, English, Chinese, ... (ru -> Russian)."""
    raw = None
    if request.language and request.language.strip():
        raw = request.language.strip()
    if not raw:
        cfg = request.audio_config or {}
        engine = cfg.get("engine") if isinstance(cfg, dict) else None
        if isinstance(engine, dict):
            lang = engine.get("language")
            if isinstance(lang, str) and lang.strip():
                raw = lang.strip()
    if not raw:
        raw = os.getenv("TTS_LANGUAGE", "ru")
    # Qwen3 ожидает полное имя: Russian, English, Chinese, ...
    lang_map = {"ru": "Russian", "en": "English", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
                "de": "German", "fr": "French", "pt": "Portuguese", "es": "Spanish", "it": "Italian"}
    return lang_map.get(raw.lower(), raw if len(raw) > 2 else "Russian")


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
    active = "qwen3" if _QWEN3_BASE is not None else "espeak" if _ESPEAK_BIN else "mock"
    # Если бэкенд qwen3, но модель не загружена — статус degraded (POST /synthesize будет 503)
    status = "ok"
    if _BACKEND in ("qwen3", "auto") and _QWEN3_BASE is None and not _QWEN3_BASE_LOADING:
        status = "degraded"
    return {
        "status": status,
        "requested_backend": _BACKEND,
        "active_backend": active,
        "qwen3_base_ready": _QWEN3_BASE is not None,
        "qwen3_base_loading": _QWEN3_BASE_LOADING,
        "qwen3_base_error": _QWEN3_BASE_ERROR,
        "qwen3_base_model": _QWEN3_BASE_MODEL_NAME,
        "qwen3_base_device": _QWEN3_BASE_DEVICE,
        "voice_clone_prompt_cache_size": len(_VOICE_CLONE_PROMPT_CACHE),
        "device_preference": _device_preference(),
        "cuda_available": cuda_ok,
        "cuda_device": cuda_name,
        "gpu_vendor": gpu_vendor,
        "gpu_hint": None if cuda_ok else "Install PyTorch with ROCm for AMD (see https://rocm.docs.amd.com) or CUDA for NVIDIA. Then restart TTS engine.",
        "default_language": os.getenv("TTS_LANGUAGE", "ru"),
        "voices_root": str(_voices_root()),
        "espeak_ready": _ESPEAK_BIN is not None,
        "voices_count": len(_get_speaker_registry()),
    }


@app.get("/voices", response_model=list[VoiceInfo])
def list_voices() -> list[VoiceInfo]:
    """Список доступных голосов. Можно заменять: добавить .wav в TTS_VOICES_ROOT или настроить voices.yaml."""
    return _list_available_voices()


def _qwen3_synthesize_internal(request: SynthesizeRequest) -> tuple[bytes, int]:
    """Синтез только через Base (voice clone). Требуется образец голоса WAV."""
    if not _init_qwen3_base() or _QWEN3_BASE is None:
        raise HTTPException(status_code=503, detail=f"Qwen3-TTS Base unavailable: {_QWEN3_BASE_ERROR}")

    language = _resolve_language(request)
    speaker_wav_path = _resolve_coqui_speaker_wav(request)
    if not speaker_wav_path or not Path(speaker_wav_path).exists():
        raise HTTPException(
            status_code=400,
            detail="Voice clone required: provide voice_sample or speaker with WAV in storage/voices",
        )
    logger.info("Qwen3 Base synthesis: wav=%s", Path(speaker_wav_path).name)

    try:
        cache_key = str(Path(speaker_wav_path).resolve())
        with _VOICE_CLONE_CACHE_LOCK:
            prompt = _VOICE_CLONE_PROMPT_CACHE.get(cache_key)
        if prompt is None:
            prompt = _QWEN3_BASE.create_voice_clone_prompt(
                ref_audio=speaker_wav_path,
                ref_text="",
                x_vector_only_mode=True,
            )
            with _VOICE_CLONE_CACHE_LOCK:
                if len(_VOICE_CLONE_PROMPT_CACHE) >= _VOICE_CLONE_CACHE_MAX:
                    _VOICE_CLONE_PROMPT_CACHE.pop(next(iter(_VOICE_CLONE_PROMPT_CACHE)), None)
                _VOICE_CLONE_PROMPT_CACHE[cache_key] = prompt
            logger.info("Voice clone prompt cached for %s", Path(speaker_wav_path).name)
        wavs, sr = _QWEN3_BASE.generate_voice_clone(
            text=request.text,
            language=language,
            voice_clone_prompt=prompt,
        )
    except Exception as e:
        logger.exception("Qwen3 voice_clone failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    if not wavs or not len(wavs):
        raise HTTPException(status_code=500, detail="Qwen3 returned no audio")

    import soundfile as sf  # noqa: PLC0415
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sf.write(tmp_path, wavs[0], sr)
        content = tmp_path.read_bytes()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    with wave.open(BytesIO(content), "rb") as wf:
        duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
    return content, duration_ms


def _qwen3_synthesize(request: SynthesizeRequest) -> Response:
    """Синтез только через Base (voice clone по WAV)."""
    content, duration_ms = _qwen3_synthesize_internal(request)
    speaker_wav_path = _resolve_coqui_speaker_wav(request)
    headers = {
        "x-duration-ms": str(duration_ms),
        "x-tts-backend": "qwen3",
        "x-tts-language": _resolve_language(request),
        "x-tts-voice-source": "clone",
        "x-tts-speaker-wav": Path(speaker_wav_path).name if speaker_wav_path else "",
    }
    if _QWEN3_BASE_DEVICE:
        headers["x-tts-device"] = _QWEN3_BASE_DEVICE
    v = _gpu_vendor()
    if v:
        headers["x-tts-gpu-vendor"] = v
    return Response(content=content, media_type="audio/wav", headers=headers)


def _batch_item_to_request(item: SynthesizeBatchItem) -> SynthesizeRequest:
    """Build a SynthesizeRequest from a batch item for resolution helpers."""
    return SynthesizeRequest(
        text=item.text,
        speaker=item.speaker,
        emotion=item.emotion or EmotionPayload(),
        language=item.language,
        voice_sample=item.voice_sample,
        audio_config=item.audio_config,
        speaker_wav_path=item.speaker_wav_path,
    )


def _qwen3_batch_synthesize(items: list[SynthesizeBatchItem]) -> list[tuple[bytes, int]]:
    """
    Batch synthesis: только Base (voice clone). Группировка по (wav_path, language).
    Для каждого элемента нужен образец голоса WAV; иначе 400.
    """
    if not items:
        return []
    resolved: list[tuple[str | None, str, SynthesizeRequest, int]] = []
    for idx, item in enumerate(items):
        req = _batch_item_to_request(item)
        lang = _resolve_language(req)
        speaker_wav = _resolve_coqui_speaker_wav(req)
        if not speaker_wav or not Path(speaker_wav).exists():
            raise HTTPException(
                status_code=400,
                detail=f"Voice clone required for batch item {idx}: provide voice_sample or speaker with WAV in storage/voices",
            )
        resolved.append((speaker_wav, lang, req, idx))
    groups: dict[tuple[str, str], list[tuple[SynthesizeRequest, int]]] = defaultdict(list)
    for wav_path, lang, req, orig_idx in resolved:
        groups[(wav_path, lang)].append((req, orig_idx))
    result_slots: list[tuple[bytes, int] | None] = [None] * len(items)
    import soundfile as sf  # noqa: PLC0415
    if not _init_qwen3_base() or _QWEN3_BASE is None:
        raise HTTPException(status_code=503, detail=f"Qwen3-TTS Base unavailable: {_QWEN3_BASE_ERROR}")
    for (wav_path, lang), group_reqs in groups.items():
        texts = [r.text for r, _ in group_reqs]
        indices = [i for _, i in group_reqs]
        try:
            with _VOICE_CLONE_CACHE_LOCK:
                prompt = _VOICE_CLONE_PROMPT_CACHE.get(str(Path(wav_path).resolve()))
            if prompt is None:
                prompt = _QWEN3_BASE.create_voice_clone_prompt(
                    ref_audio=wav_path,
                    ref_text="",
                    x_vector_only_mode=True,
                )
                with _VOICE_CLONE_CACHE_LOCK:
                    if len(_VOICE_CLONE_PROMPT_CACHE) >= _VOICE_CLONE_CACHE_MAX:
                        _VOICE_CLONE_PROMPT_CACHE.pop(next(iter(_VOICE_CLONE_PROMPT_CACHE)), None)
                    _VOICE_CLONE_PROMPT_CACHE[str(Path(wav_path).resolve())] = prompt
            wavs_list, sr = _QWEN3_BASE.generate_voice_clone(
                text=texts[0] if len(texts) == 1 else texts,
                language=lang,
                voice_clone_prompt=prompt,
            )
            if not isinstance(wavs_list, (list, tuple)):
                wavs_list = [wavs_list]
            for i, wav_data in enumerate(wavs_list):
                if i < len(indices):
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp_path = Path(tmp.name)
                    try:
                        sf.write(tmp_path, wav_data, sr)
                        content = tmp_path.read_bytes()
                    finally:
                        if tmp_path.exists():
                            tmp_path.unlink()
                    with wave.open(BytesIO(content), "rb") as wf:
                        duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
                    result_slots[indices[i]] = (content, duration_ms)
        except Exception as e:
            logger.warning("Qwen3 batch voice_clone failed for group, falling back to sequential: %s", e)
            for req, orig_idx in group_reqs:
                try:
                    content, duration_ms = _qwen3_synthesize_internal(req)
                    result_slots[orig_idx] = (content, duration_ms)
                except Exception as e2:
                    logger.exception("Qwen3 single voice_clone failed: %s", e2)
                    raise HTTPException(status_code=500, detail=str(e2))
    for i, slot in enumerate(result_slots):
        if slot is None:
            raise HTTPException(status_code=500, detail=f"Batch item {i} produced no audio")
    return [result_slots[i] for i in range(len(items))]


@app.post("/synthesize-batch")
def synthesize_batch(request: SynthesizeBatchRequest) -> SynthesizeBatchResponse:
    """Batch synthesis: только Base (voice clone); для каждого элемента нужен WAV."""
    if _require_gpu() and not _gpu_runtime_status()[0]:
        raise HTTPException(status_code=503, detail="GPU required but not available")
    if _BACKEND not in ("qwen3", "auto"):
        raise HTTPException(status_code=503, detail="Backend not qwen3")
    if not _init_qwen3_base() or _QWEN3_BASE is None:
        raise HTTPException(status_code=503, detail=f"Qwen3-TTS Base unavailable: {_QWEN3_BASE_ERROR}")
    batch_results = _qwen3_batch_synthesize(request.items)
    results = [
        SynthesizeBatchResult(content_base64=base64.b64encode(content).decode("ascii"), duration_ms=duration_ms)
        for content, duration_ms in batch_results
    ]
    return SynthesizeBatchResponse(results=results)


@app.post("/synthesize")
def synthesize(request: SynthesizeRequest) -> Response:
    _debug_log_text_to_tts(request)
    if _require_gpu() and not _gpu_runtime_status()[0]:
        raise HTTPException(status_code=503, detail="GPU required but not available (install CUDA or ROCm PyTorch)")

    if _BACKEND == "mock":
        return _mock_synthesize(request)
    if _BACKEND == "espeak":
        return _espeak_synthesize(request)

    if _BACKEND in ("qwen3", "auto"):
        if not _init_qwen3_base() or _QWEN3_BASE is None:
            if _BACKEND == "qwen3":
                raise HTTPException(status_code=503, detail=f"Qwen3-TTS Base unavailable: {_QWEN3_BASE_ERROR}")
            if not _degraded_backend_allowed():
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Qwen3-TTS Base unavailable, degraded fallback disabled. "
                        "Set TTS_ALLOW_DEGRADED_BACKEND=true for espeak/mock. "
                        f"Error: {_QWEN3_BASE_ERROR}"
                    ),
                )
            if _ESPEAK_BIN:
                return _espeak_synthesize(request)
            return _mock_synthesize(request)
        if _require_gpu() and _QWEN3_BASE_DEVICE != "cuda":
            raise HTTPException(status_code=503, detail="GPU required but Qwen3 Base is on CPU")
        return _qwen3_synthesize(request)

    if _ESPEAK_BIN:
        return _espeak_synthesize(request)
    return _mock_synthesize(request)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("TTS_ENGINE_PORT", "8020"))
    uvicorn.run(app, host="0.0.0.0", port=port)