"""
Эндпоинты озвучки через App API и пайплайн stage1–stage4.
POST /internal/process-book-stage4 запускает stage1–stage3 и формирует очередь задач;
stage4 worker дергает /internal/tts-next и /internal/tts-complete.
"""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import FileResponse

from core.models import UserBookFormat, Line, EmotionProfile, Remark
from core.pipeline.stage1_parser import StructuralParser
from core.pipeline.stage2_speaker import SpeakerResolver
from core.pipeline.stage3_emotion import EmotionResolver
from core.pipeline.stage5_tts import Stage5Assembler

# Корень app/
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_ROOT = _APP_ROOT / "storage"

# In-memory настройки голосов
_audio_settings: dict = {"config": {"voice_ids": {}}}

# Состояние пайплайна по книгам: (user_id, book_id) -> BookPipelineState
# BookPipelineState: dict с keys: lines, pending, done, stop_requested, voice_ids
_book_states: dict[tuple[str, str], dict] = {}
# Очередь (user_id, book_id) для выдачи задач в tts-next (FIFO)
_pending_books: deque[tuple[str, str]] = deque()
_lock = threading.Lock()

# Для обратной совместимости с воркером без user_id/book_id в tts-complete
_last_leased: dict | None = None


def _book_dir(user_id: str, book_id: str) -> Path | None:
    base = STORAGE_ROOT / "books" / user_id
    book_dir = (base / book_id).resolve()
    if not book_dir.exists() or not book_dir.is_dir():
        return None
    try:
        book_dir.relative_to(base.resolve())
    except ValueError:
        return None
    return book_dir


def _find_book_txt(book_dir: Path) -> Path | None:
    original_dir = book_dir / "original"
    if not original_dir.exists():
        return None
    for p in sorted(original_dir.iterdir()):
        if p.suffix.lower() == ".txt" and p.is_file():
            return p
    return None


def _emotion_to_dict(emotion: EmotionProfile | None) -> dict:
    if emotion is None:
        return {}
    return {
        "energy": emotion.energy,
        "tempo": emotion.tempo,
        "pitch": emotion.pitch,
        "pause_before": emotion.pause_before,
        "pause_after": emotion.pause_after,
    }


def _build_ubf_from_state(lines_data: list, done: dict) -> UserBookFormat:
    """Собирает UserBookFormat для stage5 из state (lines + done)."""
    line_objs = []
    for t in lines_data:
        line_id = t["line_id"]
        audio_path = done.get(line_id)
        if not audio_path:
            continue
        em = t.get("emotion") or {}
        emotion = EmotionProfile(
            energy=em.get("energy", 1.0),
            tempo=em.get("tempo", 1.0),
            pitch=em.get("pitch", 0.0),
            pause_before=em.get("pause_before", 0),
            pause_after=em.get("pause_after", 0),
        )
        line_objs.append(
            Line(
                idx=line_id,
                type="narrator",
                original=t.get("text", ""),
                remarks=[],
                is_segment=False,
                speaker=t.get("voice"),
                emotion=emotion,
                audio_path=audio_path,
            )
        )
    line_objs.sort(key=lambda l: l.idx)
    return UserBookFormat(user_id=0, book_id=0, version="v1", lines=line_objs)


def _assemble_final_audio(user_id: str, book_id: str) -> Path | None:
    """Собирает итоговый WAV (stage5) и возвращает путь к файлу. None если не все строки готовы."""
    key = (user_id, book_id)
    with _lock:
        state = _book_states.get(key)
        if not state:
            return None
        lines_data = state.get("lines") or []
        done = state.get("done") or {}
        # Если нет ни одной готовой строки — сборку не запускаем.
        if not lines_data or not done:
            return None
    out_file = STORAGE_ROOT / "books" / user_id / book_id / "final.wav"
    if out_file.exists():
        return out_file
    ubf = _build_ubf_from_state(lines_data, done)
    if not ubf.lines:
        return None
    out_file.parent.mkdir(parents=True, exist_ok=True)
    Stage5Assembler().process(ubf, out_file)
    return out_file


# --- Роутер для /books ---
books_router = APIRouter()


@books_router.get("/settings/audio")
def get_books_settings_audio():
    """GET /books/settings/audio — настройки голосов для TTS."""
    return _audio_settings


@books_router.put("/settings/audio")
def put_books_settings_audio(body: dict = Body(default_factory=dict)):
    """PUT /books/settings/audio — сохранить настройки голосов."""
    if isinstance(body.get("config"), dict):
        _audio_settings["config"] = {**_audio_settings.get("config", {}), **body["config"]}
    return _audio_settings


@books_router.get("/{book_id}")
def get_book(
    book_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """GET /books/:id — краткая информация о книге."""
    user_id = (x_user_id or "").strip() or "anonymous"
    if not _book_dir(user_id, book_id):
        raise HTTPException(status_code=404, detail="Book not found")
    key = (user_id, book_id)
    with _lock:
        state = _book_states.get(key)
    status = "uploaded"
    final_audio_path = None
    if state:
        total_lines = len(state.get("lines") or [])
        if total_lines and len(state.get("done") or {}) >= total_lines:
            status = "done"
        elif state.get("pending"):
            status = "processing"
        if status == "done":
            final_path = STORAGE_ROOT / "books" / user_id / book_id / "final.wav"
            if final_path.exists():
                final_audio_path = str(final_path)
    return {
        "id": book_id,
        "title": book_id,
        "status": status,
        "created_at": "",
        "final_audio_path": final_audio_path,
    }


@books_router.get("/{book_id}/status")
def get_book_status(
    book_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """GET /books/:id/status — прогресс озвучки (очередь и готовые строки)."""
    user_id = (x_user_id or "").strip() or "anonymous"
    if not _book_dir(user_id, book_id):
        raise HTTPException(status_code=404, detail="Book not found")
    key = (user_id, book_id)
    with _lock:
        state = _book_states.get(key)
    if not state:
        return {"stage": "idle", "progress": 0, "total_lines": 0, "tts_done": 0}
    lines = state.get("lines") or []
    done = state.get("done") or {}
    total = len(lines)
    tts_done = len(done)
    progress = int(100 * tts_done / total) if total else 0
    has_pending = bool(state.get("pending"))
    if has_pending:
        stage = "processing"
    elif tts_done > 0:
        # Очередь пуста, но есть хотя бы одна готовая строка — считаем, что сборка завершена (даже если часть строк не озвучена).
        stage = "done"
    else:
        stage = "idle"
    return {
        "stage": stage,
        "progress": progress,
        "total_lines": total,
        "tts_done": tts_done,
    }


@books_router.get("/{book_id}/download")
def download_book_audio(
    book_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """GET /books/:id/download — скачать итоговый озвученный WAV (после stage5 сборки)."""
    user_id = (x_user_id or "").strip() or "anonymous"
    if not _book_dir(user_id, book_id):
        raise HTTPException(status_code=404, detail="Book not found")
    path = _assemble_final_audio(user_id, book_id)
    if not path or not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio not ready. Finish narration and ensure all lines are done.",
        )
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{book_id}.wav",
    )


# --- Роутер для /internal ---
internal_router = APIRouter()


@internal_router.post("/process-book-stage4")
def post_process_book_stage4(
    body: dict = Body(default_factory=dict),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    POST /internal/process-book-stage4 — запуск пайплайна: stage1 (парсер), stage2 (спикеры), stage3 (эмоции),
    формирование очереди задач для stage4 (TTS). Воркер забирает задачи через /internal/tts-next.
    """
    user_id = (x_user_id or "").strip() or "anonymous"
    book_id = (body or {}).get("book_id")
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id is required")
    max_tasks = int((body or {}).get("max_tasks", 500))
    voice_ids = (body or {}).get("voice_ids") or {}
    if isinstance(voice_ids, dict):
        voice_ids = {k: v for k, v in voice_ids.items() if v}
    else:
        voice_ids = {}

    book_dir = _book_dir(user_id, book_id)
    if not book_dir:
        raise HTTPException(status_code=404, detail="Book not found")
    txt_path = _find_book_txt(book_dir)
    if not txt_path:
        raise HTTPException(status_code=404, detail="No .txt file in book original/")

    try:
        parser = StructuralParser(split_for_xtts=True)
        ubf = parser.parse_file(txt_path)
        SpeakerResolver().process(ubf)
        EmotionResolver().process(ubf)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline stage1-3 failed: {e!s}",
        ) from e

    # Собираем задачи (до max_tasks строк)
    lines_data = []
    # Мержим с настройками из /books/settings/audio
    config_voice_ids = (_audio_settings.get("config") or {}).get("voice_ids") or {}
    effective_voice_ids: dict[str, str] = {}
    for role in ("narrator", "male", "female"):
        if isinstance(voice_ids, dict) and voice_ids.get(role):
            effective_voice_ids[role] = str(voice_ids[role])
        elif isinstance(config_voice_ids, dict) and config_voice_ids.get(role):
            effective_voice_ids[role] = str(config_voice_ids[role])

    for line in sorted(ubf.lines, key=lambda l: l.idx):
        if len(lines_data) >= max_tasks:
            break
        if not (line.original or "").strip():
            continue
        # Определяем роль для строки и подставляем выбранный пользователем голос.
        role = line.speaker or "narrator"
        voice_override = effective_voice_ids.get(role)
        # Если для роли выбран конкретный voiceId, передаём его как speaker в TTS;
        # иначе оставляем роль (narrator/male/female), и движок возьмёт дефолтный голос.
        voice_for_tts = voice_override or role
        lines_data.append({
            "line_id": line.idx,
            "text": line.original.strip(),
            "voice": voice_for_tts,
            "emotion": _emotion_to_dict(line.emotion),
            "audio_config": {"voice_ids": effective_voice_ids} if effective_voice_ids else None,
        })

    pending = deque([t["line_id"] for t in lines_data])
    key = (user_id, book_id)
    with _lock:
        _book_states[key] = {
            "lines": lines_data,
            "pending": pending,
            "done": {},
            "stop_requested": False,
            "voice_ids": effective_voice_ids,
        }
        # Добавляем в очередь на выдачу (без дубликатов подряд)
        if key not in _pending_books:
            _pending_books.append(key)

    return {
        "book_id": book_id,
        "processed_tasks": 0,
        "remaining_tasks": len(pending),
        "book_status": "processing",
        "final_audio_path": None,
        "stopped": False,
    }


@internal_router.post("/tts-next")
def post_tts_next():
    """
    POST /internal/tts-next — выдать следующую задачу для TTS (вызывается stage4 worker).
    Возвращает 404, если очереди пусты.
    """
    global _last_leased
    with _lock:
        while _pending_books:
            key = _pending_books[0]
            state = _book_states.get(key)
            if not state or state.get("stop_requested"):
                _pending_books.popleft()
                continue
            pending = state.get("pending")
            if not pending:
                _pending_books.popleft()
                continue
            line_id = pending.popleft()
            lines = state.get("lines") or []
            task = next((t for t in lines if t["line_id"] == line_id), None)
            if not task:
                continue
            user_id, book_id = key
            task_id = f"{book_id}_{line_id}"
            _last_leased = {"user_id": user_id, "book_id": book_id, "line_id": line_id}
            return {
                "task_id": task_id,
                "user_id": user_id,
                "book_id": book_id,
                "line_id": line_id,
                "text": task["text"],
                "voice": task["voice"],
                "emotion": task.get("emotion") or {},
                "audio_config": task.get("audio_config"),
            }
    raise HTTPException(status_code=404, detail="No pending tasks")


@internal_router.post("/tts-complete")
def post_tts_complete(body: dict = Body(default_factory=dict)):
    """
    POST /internal/tts-complete — отметить строку озвученной (вызывается stage4 worker).
    Тело: line_id, audio_path; желательно также user_id и book_id (иначе используется last leased).
    """
    global _last_leased
    data = body or {}
    line_id = data.get("line_id")
    audio_path = data.get("audio_path")
    if line_id is None or not audio_path:
        raise HTTPException(status_code=400, detail="line_id and audio_path required")
    user_id = data.get("user_id")
    book_id = data.get("book_id")
    if not user_id or not book_id:
        if _last_leased and _last_leased.get("line_id") == line_id:
            user_id = _last_leased.get("user_id")
            book_id = _last_leased.get("book_id")
            _last_leased = None
        if not user_id or not book_id:
            raise HTTPException(status_code=400, detail="user_id and book_id required (or matching last tts-next)")
    key = (user_id, book_id)
    with _lock:
        state = _book_states.get(key)
        if not state:
            raise HTTPException(status_code=404, detail="Book state not found")
        state.setdefault("done", {})[line_id] = audio_path
    return {"line_id": line_id, "audio_path": audio_path, "book_id": book_id}


@internal_router.post("/stop-book-stage4")
def post_stop_book_stage4(body: dict = Body(default_factory=dict)):
    """POST /internal/stop-book-stage4 — запрос остановки озвучки книги."""
    book_id = (body or {}).get("book_id") or ""
    # Пометить все книги с этим book_id (любой user) или только по текущему user — по контракту приходит только book_id
    with _lock:
        for key, state in list(_book_states.items()):
            if key[1] == book_id:
                state["stop_requested"] = True
    return {"book_id": book_id, "stop_requested": True}
