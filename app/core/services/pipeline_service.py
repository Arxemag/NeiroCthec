from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Book, BookStatus, Line, LineStatus, TTSTask


def run_stage0(db: Session, book: Book) -> None:
    if book.status not in {BookStatus.uploaded, BookStatus.error}:
        return

    source = Path(book.source_path)
    if not source.exists():
        book.status = BookStatus.error
        return

    book.status = BookStatus.parsing

    with source.open("r", encoding="utf-8") as fh:
        for idx, raw in enumerate(fh, start=1):
            original = raw.strip()
            if not original:
                continue
            line_type = "dialogue" if original.startswith("—") else "narrator"
            db.add(
                Line(
                    book_id=book.id,
                    idx=idx,
                    type=line_type,
                    speaker="narrator",
                    original=original,
                    segments=[{"text": original, "kind": line_type}],
                    tts_status=LineStatus.new,
                )
            )


def run_stage1(db: Session, book: Book) -> None:
    lines = db.scalars(select(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.new)).all()
    for line in lines:
        line.tts_status = LineStatus.stage1_done


def run_stage2(db: Session, book: Book) -> None:
    lines = db.scalars(select(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.stage1_done)).all()
    for line in lines:
        line.type = line.type or "narrator"
        if line.type == "dialogue" and line.speaker == "narrator":
            line.speaker = "male"
        line.segments = line.segments or [{"text": line.original, "kind": line.type}]
        line.tts_status = LineStatus.stage2_done


def run_stage3(db: Session, book: Book) -> None:
    lines = db.scalars(select(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.stage2_done)).all()
    for line in lines:
        line.emotion = line.emotion or {
            "energy": 1.0,
            "tempo": 1.0,
            "pitch": 0.0,
            "pause_before": 0,
            "pause_after": 150,
        }
        line.tts_status = LineStatus.tts_pending
        if not line.tts_task:
            db.add(TTSTask(line_id=line.id, payload={"line_id": line.id, "user_id": book.user_id, "book_id": book.id, "text": line.original, "emotion": line.emotion, "voice": line.speaker}))


def update_book_status(db: Session, book: Book) -> None:
    total = db.scalar(select(func.count()).select_from(Line).where(Line.book_id == book.id)) or 0
    if total == 0:
        return

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
    elif tts_done > 0 or db.scalar(
        select(func.count()).select_from(Line).where(Line.book_id == book.id, Line.tts_status == LineStatus.tts_pending)
    ):
        book.status = BookStatus.tts_processing
    else:
        book.status = BookStatus.analyzed


def try_stage5_assemble(db: Session, book: Book, output_root: Path) -> None:
    lines = db.scalars(select(Line).where(Line.book_id == book.id).order_by(Line.idx.asc())).all()
    if not lines:
        return
    if any(line.tts_status != LineStatus.tts_done for line in lines):
        return

    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / f"{book.id}.mp3"
    with target.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(f"{line.idx}:{line.audio_path}\n")
            line.tts_status = LineStatus.assembled

    book.final_audio_path = str(target)
    book.status = BookStatus.completed


def run_contract_pipeline(db: Session, book: Book, output_root: Path) -> None:
    run_stage0(db, book)
    run_stage1(db, book)
    run_stage2(db, book)
    run_stage3(db, book)
    update_book_status(db, book)
    try_stage5_assemble(db, book, output_root)
