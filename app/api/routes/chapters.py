from fastapi import APIRouter, HTTPException
from pathlib import Path

from core.pipeline.stage1_parser import StructuralParser
from core.pipeline.stage2_speaker import SpeakerResolver
from core.pipeline.stage3_emotion import EmotionResolver
from core.pipeline.stage4_voice import VoiceSynthesizer
from core.pipeline.stage5_tts import Stage5Assembler

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
    tts = VoiceSynthesizer()
    assembler = Stage5Assembler()

    ubf = parser.parse_file(text_path)
    speaker.process(ubf)
    emotion.process(ubf)
    tts.process(ubf, out_dir=chapter_dir / "segments")

    out_audio = chapter_dir / "audio.wav"
    assembler.process(ubf, out_file=out_audio)

    return {
        "chapter_id": chapter_id,
        "status": "done",
        "audio_path": str(out_audio)
    }
