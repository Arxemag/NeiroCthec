import io
import uuid
import wave
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.schemas.voice import VoiceOut, VoiceUploadResponse
from core.voices import (
    BUILTIN_VOICE_IDS,
    get_voice_path,
    get_voice_registry,
    _user_voices_dir,
)

router = APIRouter()

# Ограничения загрузки своего голоса
MAX_VOICE_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_VOICE_DURATION_SEC = 30.0


def _validate_wav_content(data: bytes) -> tuple[bool, str | None]:
    """Проверяет, что data — валидный WAV, опционально длительность до 30 с. Возвращает (ok, error_message)."""
    if len(data) < 44:
        return False, "File too small to be a valid WAV"
    if not (data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
        return False, "Only WAV format is allowed"
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            nframes = w.getnframes()
            rate = w.getframerate()
            if rate <= 0:
                return False, "Invalid WAV sample rate"
            duration_sec = nframes / float(rate)
            if duration_sec > MAX_VOICE_DURATION_SEC:
                return False, f"Duration must not exceed {MAX_VOICE_DURATION_SEC}s"
    except Exception as e:
        return False, f"Invalid WAV: {e!s}"
    return True, None


@router.get("/voices", response_model=list[VoiceOut])
def list_voices(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    Список доступных голосов: встроенные (narrator, male, female) + при X-User-Id свои из storage/voices/{user_id}/.
    """
    # #region agent log
    try:
        import json
        _log = {"sessionId": "9376b5", "hypothesisId": "voices-core", "location": "voices.py:list_voices", "message": "Core list_voices", "data": {"x_user_id": (x_user_id or "")[:8] if x_user_id else None}, "timestamp": __import__("time").time() * 1000}
        _f = open("debug-9376b5.log", "a", encoding="utf-8")
        _f.write(json.dumps(_log, ensure_ascii=False) + "\n")
        _f.close()
    except Exception:
        pass
    # #endregion
    registry = get_voice_registry(user_id=x_user_id)
    # #region agent log
    try:
        import json as _json
        _log2 = {"sessionId": "9376b5", "hypothesisId": "voices-core", "location": "voices.py:list_voices", "message": "Core list_voices result", "data": {"count": len(registry)}, "timestamp": __import__("time").time() * 1000}
        _f2 = open("debug-9376b5.log", "a", encoding="utf-8")
        _f2.write(_json.dumps(_log2, ensure_ascii=False) + "\n")
        _f2.close()
    except Exception:
        pass
    # #endregion
    return [
        VoiceOut(
            id=v["id"],
            name=v["name"],
            role=v["role"],
            sample_url=f"/voices/{v['id']}/sample",
        )
        for v in registry
    ]


@router.post("/voices/upload", response_model=VoiceUploadResponse)
async def upload_voice(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    Загрузка своего голоса (WAV). Обязателен заголовок X-User-Id.
    Валидация: только WAV, до 5 MB, длительность до 30 с. Сохраняется в storage/voices/{user_id}/{voice_id}.wav.
    """
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Only WAV files are allowed")
    content = await file.read()
    if len(content) > MAX_VOICE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size must not exceed {MAX_VOICE_UPLOAD_BYTES // (1024*1024)} MB",
        )
    ok, err = _validate_wav_content(content)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Invalid WAV")
    voice_id = str(uuid.uuid4())
    user_dir = _user_voices_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    out_path = user_dir / f"{voice_id}.wav"
    out_path.write_bytes(content)
    return VoiceUploadResponse(id=voice_id, name=file.filename)


@router.get("/voices/{voice_id}/sample")
def get_voice_sample(
    voice_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    Отдаёт WAV-файл сэмпла голоса по id. Сначала общий реестр; если не найден — при X-User-Id свой голос.
    """
    path = get_voice_path(voice_id, user_id=None)
    if not path and x_user_id:
        path = get_voice_path(voice_id, user_id=x_user_id)
    if not path:
        raise HTTPException(status_code=404, detail="Voice not found")
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Sample file not found")
    return FileResponse(p, media_type="audio/wav")


@router.delete("/voices/{voice_id}", status_code=204)
def delete_voice(
    voice_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    Удаление своего голоса. Только для своих (storage/voices/{user_id}/{voice_id}.wav). Встроенные удалять нельзя.
    """
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    if voice_id in BUILTIN_VOICE_IDS:
        raise HTTPException(status_code=400, detail="Cannot delete built-in voice")
    user_dir = _user_voices_dir(user_id)
    target = user_dir / f"{voice_id}.wav"
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Voice not found")
    try:
        target.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {e!s}") from e
    return None
