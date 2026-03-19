from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/{chapter_id}/process")
def process_chapter(chapter_id: int):
    # Coqui TTS удалён. Озвучка только через stage4 worker + Qwen3 (tts_engine_service).
    raise HTTPException(
        503,
        detail="Обработка глав через этот эндпоинт отключена. Озвучка книг — через основной пайплайн: stage4 worker и Qwen3 (divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit, tts_engine_service).",
    )
