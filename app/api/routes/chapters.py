from fastapi import APIRouter, HTTPException
from pathlib import Path

from core.models import Line, UserBookFormat
from core.integrations.stage4_tts_client import Stage4TTSClient
from core.pipeline.stage5_tts import Stage5Assembler

router = APIRouter()

STORAGE_ROOT = Path("storage")


def _read_lines(text_path: Path, chapter_id: int) -> UserBookFormat:
    lines: list[Line] = []
    with text_path.open("r", encoding="utf-8") as source:
        for idx, raw in enumerate(source, start=1):
            original = raw.strip()
            if not original:
                continue
            line_type = "dialogue" if original.startswith("—") else "narrator"
            line = Line(id=idx, chapter_id=chapter_id, type=line_type, original=original, idx=idx)
            line.speaker = "narrator"
            lines.append(line)
    return UserBookFormat(lines=lines)


@router.post("/{chapter_id}/process")
def process_chapter(chapter_id: int):
    chapter_dir = STORAGE_ROOT / "chapters" / str(chapter_id)
    text_path = chapter_dir / "text.txt"
    if not text_path.exists():
        raise HTTPException(404, "Chapter text not found")

    ubf = _read_lines(text_path, chapter_id)
    if not ubf.lines:
        raise HTTPException(400, "Chapter has no lines to process")

    stage4_client = Stage4TTSClient()
    assembler = Stage5Assembler()

    tts_results = []
    for line in ubf.lines:
        result = stage4_client.synthesize_line(
            user_id=f"chapter-{chapter_id}",
            book_id="single-book",
            line=line,
            speaker=line.speaker or "narrator",
        )

        # Stage 5 склеивает фрагменты, полученные от Stage 4
        line.stage4_audio_uri = result.get("audio_uri")
        line.audio_path = result.get("audio_uri")
        tts_results.append(result)

    out_audio = chapter_dir / "audio.wav"
    assembler.process(ubf, out_file=out_audio)

    return {
        "chapter_id": chapter_id,
        "status": "done",
        "audio_path": str(out_audio),
        "tts_tasks": tts_results,
    }
