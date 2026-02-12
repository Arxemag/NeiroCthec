from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import NormalizedBook, UserBookFormat
from core.pipeline.stage0_format_detector import FormatDetector
from core.pipeline.stage0_format_parser import FormatParser
from core.pipeline.stage0_text_extractor import TextExtractor
from core.pipeline.stage1_1_chapter_parser import ChapterParser
from core.pipeline.stage1_2_line_type_parser import LineTypeParser
from core.pipeline.stage1_3_segment_analyzer import SegmentAnalyzer
from core.pipeline.stage1_4_segment_text_adapter import SegmentTextAdapter
from core.pipeline.stage1_5_stress import StressPlaceholder
from core.pipeline.stage2_speaker_resolver import SpeakerResolver
from core.pipeline.stage3_tts_director import TTSDirector
from db.models import Book, BookStatus, Line, LineStatus, TTSTask, TaskStatus

DEFAULT_EMOTION = {
    "energy": 1.0,
    "tempo": 1.0,
    "pitch": 0.0,
    "pause_before": 0,
    "pause_after": 150,
}


# -----------------------------
# Stage 0-3 orchestration (core)
# -----------------------------

def run_stage0(db: Session, book: Book) -> list:
    """Stage 0: detect/parse/extract source text into normalized raw lines."""
    source = Path(book.source_path)
    if not source.exists():
        book.status = BookStatus.error
        return []

    fmt = FormatDetector().detect(source)
    raw_text = FormatParser().parse(source, fmt)
    normalized = TextExtractor().extract(raw_text, fmt)
    book.status = BookStatus.parsing
    return normalized.lines


def run_stage1(normalized_lines: list) -> list:
    """Stage 1: chapter parsing + line typing."""
    chapters = ChapterParser().parse(NormalizedBook(raw_text="", lines=normalized_lines, source_format="txt"))
    return LineTypeParser().parse(chapters)


def run_stage2(stage1_lines: list) -> list:
    """Stage 2: speaker resolver (2.0-2.4 via resolver internals)."""
    for idx, line in enumerate(stage1_lines):
        line.idx = idx
        if getattr(line, "remarks", None) is None:
            line.remarks = []
    ubf = UserBookFormat(lines=stage1_lines)
    return SpeakerResolver().process(ubf).lines


def run_stage3(stage2_lines: list) -> list[dict]:
    """Stage 3: segment prep + stress + tts meta + emotion contract payloads."""
    analyzer = SegmentAnalyzer()
    adapter = SegmentTextAdapter()
    stress = StressPlaceholder()
    tts_director = TTSDirector()

    rendered: list[dict] = []
    for idx, line in enumerate(stage2_lines):
        segments = analyzer.split(line)
        serialized_segments: list[dict] = []

        for seg_idx, segment in enumerate(segments):
            segment.speaker = line.speaker
            adapter.adapt(segment, is_last=seg_idx == len(segments) - 1)
            stress.apply(segment)
            tts_director.apply(segment)
            serialized_segments.append(
                {
                    "id": segment.id,
                    "line_id": segment.line_id,
                    "chapter_id": line.chapter_id,
                    "kind": segment.kind,
                    "speaker": segment.speaker,
                    "original_text": segment.original_text,
                    "tts_text": segment.tts_text,
                    "stress_map": segment.stress_map or [],
                    "tts_meta": vars(segment.tts_meta) if segment.tts_meta else {},
                }
            )

        rendered.append(
            {
                "idx": idx,
                "chapter_id": line.chapter_id,
                "type": line.type or "narrator",
                "speaker": line.speaker or "narrator",
                "original": line.original,
                "segments": serialized_segments,
                "emotion": dict(DEFAULT_EMOTION),
                "tts_status": LineStatus.tts_pending,
            }
        )

    return rendered


def _has_audio_progress(db: Session, book_id: str) -> bool:
    progressed = db.scalar(
        select(func.count())
        .select_from(Line)
        .where(Line.book_id == book_id, Line.tts_status.in_([LineStatus.tts_done, LineStatus.assembled]))
    ) or 0
    return progressed > 0


def _replace_book_lines_and_tasks(db: Session, book: Book, stage3_payloads: list[dict]) -> None:
    """Persist stage0-3 result atomically for one book before Stage4."""
    line_ids = db.scalars(select(Line.id).where(Line.book_id == book.id)).all()
    if line_ids:
        db.query(TTSTask).filter(TTSTask.line_id.in_(line_ids)).delete(synchronize_session=False)
    db.query(Line).filter(Line.book_id == book.id).delete(synchronize_session=False)

    for line_payload in stage3_payloads:
        db_line = Line(
            book_id=book.id,
            idx=line_payload["idx"],
            type=line_payload["type"],
            speaker=line_payload["speaker"],
            original=line_payload["original"],
            segments=line_payload["segments"],
            emotion=line_payload["emotion"],
            tts_status=LineStatus.tts_pending,
        )
        db.add(db_line)
        db.flush()

        db.add(
            TTSTask(
                line_id=db_line.id,
                status=TaskStatus.pending,
                payload={
                    "line_id": db_line.id,
                    "user_id": book.user_id,
                    "book_id": book.id,
                    "text": db_line.original,
                    "emotion": db_line.emotion,
                    "voice": db_line.speaker,
                    "chapter_id": line_payload["chapter_id"],
                },
            )
        )


# -----------------------------
# Stage 4 separate worker hooks
# -----------------------------

def stage4_mark_done(db: Session, line: Line, audio_path: str) -> None:
    """Mark a single line as produced by the external Stage4 service."""
    line.audio_path = audio_path
    line.tts_status = LineStatus.tts_done
    if line.tts_task:
        line.tts_task.status = TaskStatus.done


# -----------------------------
# Stage 5 chapter assembly
# -----------------------------

def _extract_chapter_id(line: Line) -> int:
    if line.segments and isinstance(line.segments, list):
        first = line.segments[0] if line.segments else {}
        if isinstance(first, dict):
            value = first.get("chapter_id")
            if isinstance(value, int):
                return value
    return 0


def try_stage5_assemble(db: Session, book: Book, output_root: Path) -> None:
    """Stage 5: assemble per chapter after all Stage4 lines are ready."""
    lines = db.scalars(select(Line).where(Line.book_id == book.id).order_by(Line.idx.asc())).all()
    if not lines:
        return
    if any(line.tts_status != LineStatus.tts_done for line in lines):
        return

    book_root = output_root / book.user_id / book.id
    chapters_root = book_root / "chapters"
    chapters_root.mkdir(parents=True, exist_ok=True)

    by_chapter: dict[int, list[Line]] = defaultdict(list)
    for line in lines:
        by_chapter[_extract_chapter_id(line)].append(line)

    chapter_outputs: list[Path] = []
    for chapter_id in sorted(by_chapter):
        chapter_file = chapters_root / f"chapter_{chapter_id:03d}.mp3"
        with chapter_file.open("w", encoding="utf-8") as fh:
            for line in by_chapter[chapter_id]:
                fh.write(f"{line.idx}:{line.audio_path}\n")
                line.tts_status = LineStatus.assembled
        chapter_outputs.append(chapter_file)

    final_index = book_root / f"{book.id}.mp3"
    with final_index.open("w", encoding="utf-8") as fh:
        for path in chapter_outputs:
            fh.write(f"{path.name}\n")

    book.final_audio_path = str(final_index)
    book.status = BookStatus.completed


def update_book_status(db: Session, book: Book) -> None:
    total = db.scalar(select(func.count()).select_from(Line).where(Line.book_id == book.id)) or 0
    if total == 0:
        return

    tts_pending = db.scalar(
        select(func.count()).select_from(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.tts_pending)
    ) or 0
    tts_done = db.scalar(
        select(func.count()).select_from(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.tts_done)
    ) or 0
    assembled = db.scalar(
        select(func.count()).select_from(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.assembled)
    ) or 0

    if assembled == total:
        book.status = BookStatus.completed
    elif tts_done == total:
        book.status = BookStatus.assembling
    elif tts_pending > 0 or tts_done > 0:
        book.status = BookStatus.tts_processing
    else:
        book.status = BookStatus.analyzed


def run_contract_pipeline(db: Session, book: Book, output_root: Path) -> None:
    """
    Contract orchestrator:
      - Stage 0-3 are always executed together inside API core.
      - Stage 4 is always external worker, consuming TTSTask.
      - Stage 5 runs only after Stage4 completed all lines.
    """
    # Do not rebuild 0-3 once Stage4 already produced line audio.
    if not _has_audio_progress(db, book.id):
        stage0_lines = run_stage0(db, book)
        if not stage0_lines:
            return

        stage1_lines = run_stage1(stage0_lines)
        stage2_lines = run_stage2(stage1_lines)
        stage3_payloads = run_stage3(stage2_lines)
        _replace_book_lines_and_tasks(db, book, stage3_payloads)

    update_book_status(db, book)
    try_stage5_assemble(db, book, output_root)
