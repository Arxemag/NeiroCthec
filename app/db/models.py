from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class BookStatus(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    analyzed = "analyzed"
    tts_processing = "tts_processing"
    assembling = "assembling"
    completed = "completed"
    error = "error"


class LineStatus(str, Enum):
    new = "new"
    stage1_done = "stage1_done"
    stage2_done = "stage2_done"
    stage3_done = "stage3_done"
    tts_pending = "tts_pending"
    tts_done = "tts_done"
    assembled = "assembled"
    error = "error"


class TaskStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    source_path: Mapped[str] = mapped_column(String(1024))
    final_audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[BookStatus] = mapped_column(SAEnum(BookStatus), default=BookStatus.uploaded, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lines: Mapped[list[Line]] = relationship(back_populates="book", cascade="all, delete-orphan")


class Line(Base):
    __tablename__ = "lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(64), default="narrator")
    speaker: Mapped[str] = mapped_column(String(64), default="narrator")
    original: Mapped[str] = mapped_column(Text)
    segments: Mapped[list] = mapped_column(JSON, default=list)
    emotion: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tts_status: Mapped[LineStatus] = mapped_column(SAEnum(LineStatus), default=LineStatus.new, index=True)
    audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book: Mapped[Book] = relationship(back_populates="lines")
    tts_task: Mapped[TTSTask | None] = relationship(back_populates="line", uselist=False, cascade="all, delete-orphan")


class TTSTask(Base):
    __tablename__ = "tts_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    line_id: Mapped[str] = mapped_column(ForeignKey("lines.id", ondelete="CASCADE"), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.pending, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    line: Mapped[Line] = relationship(back_populates="tts_task")


Index("ix_lines_book_stage", Line.book_id, Line.tts_status)
Index("ix_lines_book_idx", Line.book_id, Line.idx)
