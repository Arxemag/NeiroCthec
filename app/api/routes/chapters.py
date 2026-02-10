from fastapi import APIRouter, HTTPException
from pathlib import Path

from core.pipeline.stage1_parser import StructuralParser
from core.pipeline.stage2_speaker import SpeakerResolver
from core.pipeline.stage3_emotion import EmotionResolver
from core.integrations.stage4_tts_client import Stage4TTSClient

router = APIRouter()

STORAGE_ROOT = Path("storage")


@router.post("/{chapter_id}/process")
def process_chapter(chapter_id: int):
    chapter_dir = STORAGE_ROOT / "chapters" / str(chapter_id)

    text_path = chapter_dir / "text.txt"
    if not text_path.exists():
        raise HTTPException(404, "Chapter text not found")

    parser = StructuralParser()
    speaker = SpeakerResolver()
    emotion = EmotionResolver()
    stage4_client = Stage4TTSClient()

    ubf = parser.parse_file(text_path)
    speaker.process(ubf)
    emotion.process(ubf)

    tts_results = []
    for line in ubf.lines:
        if not line.original.strip():
            continue

        result = stage4_client.synthesize_line(
            user_id=f"chapter-{chapter_id}",
            book_id="single-book",
            line=line,
            speaker=line.speaker or "narrator",
        )
        tts_results.append(result)

    return {
        "chapter_id": chapter_id,
        "status": "done",
        "tts_tasks": tts_results,
    }
