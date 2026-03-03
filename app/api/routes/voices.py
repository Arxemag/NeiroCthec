from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.schemas.voice import VoiceOut
from core.voices import get_voice_registry, get_voice_path

router = APIRouter()


@router.get("/voices", response_model=list[VoiceOut])
def list_voices():
    """
    Список доступных голосов с ролями для выбора в проекте:
    narrator — Диктор, male — Мужской голос, female — Женский голос.
    """
    registry = get_voice_registry()
    return [
        VoiceOut(
            id=v["id"],
            name=v["name"],
            role=v["role"],
            sample_url=f"/voices/{v['id']}/sample",
        )
        for v in registry
    ]


@router.get("/voices/{voice_id}/sample")
def get_voice_sample(voice_id: str):
    """Отдаёт WAV-файл сэмпла голоса по id."""
    path = get_voice_path(voice_id)
    if not path:
        raise HTTPException(status_code=404, detail="Voice not found")
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Sample file not found")
    return FileResponse(path, media_type="audio/wav")
