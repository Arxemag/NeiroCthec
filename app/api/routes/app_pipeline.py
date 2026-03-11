"""
Эндпоинты озвучки через App API и пайплайн stage1–stage4.
POST /internal/process-book-stage4 запускает stage1–stage3 и формирует очередь задач;
stage4 worker дергает /internal/tts-next и /internal/tts-complete.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
from pathlib import Path
from urllib.parse import quote, unquote

from collections import defaultdict, deque

import requests

_log = logging.getLogger(__name__)

# Имя файла с последними voice_ids по книге (для переиспользования уже озвученных строк)
_BOOK_CONFIG_FILENAME = "config.json"

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import FileResponse

from core.models import UserBookFormat, Line, EmotionProfile, Remark
from core.pipeline.stage1_parser import StructuralParser
from core.pipeline.tts_normalize import normalize_text_for_tts
from core.voices import get_voice_path
from core.pipeline.stage2_speaker import SpeakerResolver
from core.pipeline.stage2_post_chunk import process as post_chunk_process
from core.pipeline.stage3_emotion import EmotionResolver
from core.pipeline.stage5_tts import Stage5Assembler

# Корень app/
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
_storage_env = os.environ.get("APP_STORAGE_ROOT") or os.environ.get("CORE_STORAGE_PATH")
STORAGE_ROOT = Path(_storage_env) if _storage_env else _APP_ROOT / "storage"


# In-memory настройки голосов (tts_engine: qwen3 | xtts2)
_audio_settings: dict = {"config": {"voice_ids": {}, "tts_engine": "qwen3"}}

# Состояние пайплайна по книгам: (user_id, book_id) -> BookPipelineState
# BookPipelineState: dict с keys: lines, pending, done, stop_requested, voice_ids
_book_states: dict[tuple[str, str], dict] = {}
# Очередь (user_id, book_id) для выдачи задач в tts-next (FIFO)
_pending_books: deque[tuple[str, str]] = deque()
_lock = threading.Lock()

# Для обратной совместимости с воркером без user_id/book_id в tts-complete
_last_leased: dict | None = None
# Для tts-complete-batch: список последних выданных задач
_last_leased_batch: list[dict] | None = None

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
    """Ищем текст для пайплайна: предпочтительно extracted.txt (из fb2/epub/mobi), иначе любой .txt."""
    original_dir = book_dir / "original"
    if not original_dir.exists():
        return None
    extracted = original_dir / "extracted.txt"
    if extracted.is_file():
        return extracted
    for p in sorted(original_dir.iterdir()):
        if p.suffix.lower() == ".txt" and p.is_file():
            return p
    return None


def _load_book_voice_config(book_dir: Path) -> tuple[dict[str, str], str | None, dict]:
    """
    Читает сохранённые voice_ids, tts_engine и speaker_settings книги.
    Возвращает (voice_ids, tts_engine, speaker_settings). speaker_settings: { narrator|male|female: { tempo, pitch } }.
    """
    path = book_dir / _BOOK_CONFIG_FILENAME
    voice_ids: dict[str, str] = {}
    tts_engine: str | None = None
    speaker_settings: dict = {}
    if not path.exists():
        return (voice_ids, tts_engine, speaker_settings)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            v = data.get("voice_ids")
            if isinstance(v, dict):
                voice_ids = {k: str(v[k]) for k in ("narrator", "male", "female") if v.get(k)}
            tts_engine = data.get("tts_engine")
            if not isinstance(tts_engine, str):
                tts_engine = None
            ss = data.get("speaker_settings")
            if isinstance(ss, dict):
                speaker_settings = {
                    k: {"tempo": float(ss[k].get("tempo", 1.0)), "pitch": float(ss[k].get("pitch", 0.0))}
                    for k in ("narrator", "male", "female")
                    if isinstance(ss.get(k), dict)
                }
    except Exception:
        pass
    return (voice_ids, tts_engine, speaker_settings)


def _save_book_voice_config(
    book_dir: Path,
    voice_ids: dict[str, str],
    tts_engine: str | None = None,
    speaker_settings: dict | None = None,
) -> None:
    """Сохраняет voice_ids, tts_engine и speaker_settings книги."""
    book_dir.mkdir(parents=True, exist_ok=True)
    path = book_dir / _BOOK_CONFIG_FILENAME
    payload: dict = {"voice_ids": voice_ids}
    if tts_engine:
        payload["tts_engine"] = tts_engine
    if speaker_settings is not None:
        payload["speaker_settings"] = speaker_settings
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")


def _save_processed_text_with_roles(book_dir: Path, ubf: UserBookFormat) -> None:
    """
    Сохраняет обработанный текст с назначенными ролями в processed/text_with_roles.txt.
    Используется текст для TTS (text_for_tts), если задан — так в storage лежит уже отредактированный вариант.
    Формат: [ROLE] текст строки
    """
    processed_dir = book_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "text_with_roles.txt"

    lines_output = []
    for line in sorted(ubf.lines, key=lambda l: l.idx):
        text = (getattr(line, "text_for_tts", None) or line.original or "").strip()
        if not text:
            continue
        role = line.speaker or "narrator"
        line_type = line.type or "prose"
        lines_output.append(f"[{role.upper()}] ({line_type}) {text}")

    output_path.write_text("\n".join(lines_output), encoding="utf-8")


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


def _speaker_settings_to_emotion(speaker_settings: dict, role: str) -> dict:
    """В TTS передаём только tempo и pitch из speaker_settings[role]. Остальное — дефолты/игнор."""
    s = (speaker_settings or {}).get(role) if isinstance(speaker_settings, dict) else None
    if not isinstance(s, dict):
        return {"tempo": 1.0, "pitch": 0.0}
    return {
        "tempo": float(s.get("tempo", 1.0)),
        "pitch": float(s.get("pitch", 0.0)),
    }


def _split_text_for_xtts(text: str, max_len: int = 100) -> list[str]:
    """
    Ограничивает длину чанков для XTTS2 (по умолчанию 100 символов).
    Режем только по точке: от границы max_len ищем точку влево и вправо, режем по той, что ближе.
    По пробелу не режем.
    """
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= max_len:
        return [t]
    parts: list[str] = []
    start = 0
    while start < len(t):
        boundary = min(start + max_len, len(t))
        if boundary >= len(t):
            part = t[start:].strip()
            if part:
                parts.append(part)
            break
        # Ищем точку влево от boundary (в [start, boundary))
        left_dot = t.rfind(".", start, boundary)
        cut_left = (left_dot + 1) if left_dot >= 0 else -1
        # Ищем точку вправо от boundary (в [boundary, boundary + max_len])
        right_span = min(boundary + max_len, len(t))
        right_dot = t.find(".", boundary, right_span)
        cut_right = (right_dot + 1) if right_dot >= 0 else -1

        if cut_left >= 0 and cut_right >= 0:
            # Обе найдены — режем по той, что ближе к boundary
            if (boundary - cut_left) <= (cut_right - boundary):
                cut = cut_left
            else:
                cut = cut_right
        elif cut_left >= 0:
            cut = cut_left
        elif cut_right >= 0:
            cut = cut_right
        else:
            # Точки нет — жёсткий разрез по boundary (по пробелу не режем)
            cut = boundary
        part = t[start:cut].strip()
        if part:
            parts.append(part)
        start = cut
    return parts


def _build_ubf_from_state(lines_data: list, done: dict) -> UserBookFormat:
    """Собирает UserBookFormat для stage5 из state (lines + done). Пути к WAV приводятся к абсолютным."""
    line_objs = []
    for t in lines_data:
        line_id = t["line_id"]
        audio_path = done.get(line_id)
        if not audio_path:
            continue
        p = Path(audio_path)
        if not p.is_absolute():
            audio_path = str((STORAGE_ROOT / audio_path).resolve())
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
                type=t.get("type") or "narrator",
                original=t.get("text", ""),
                remarks=[],
                is_segment=False,
                chapter_id=t.get("chapter_id"),
                is_chapter_header=bool(t.get("is_chapter_header")),
                speaker=t.get("voice"),
                emotion=emotion,
                audio_path=audio_path,
            )
        )
    # Сортировка: при XTTS-разбиении line_id = base*1000+pi; числовая сортировка дала бы 5,6,5001,5002.
    # Сортируем по (base, part), чтобы порядок был 5,5001,5002,6.
    def _line_sort_key(l: Line) -> tuple:
        i = l.idx
        if i >= 1000:
            return (i // 1000, i % 1000)
        return (i, 0)
    line_objs.sort(key=_line_sort_key)
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
    # Удаляем старый final.wav, чтобы сборка всегда писала новый (при смене голосов старый файл не должен отдаваться).
    if out_file.exists():
        try:
            out_file.unlink()
        except OSError:
            pass
    ubf = _build_ubf_from_state(lines_data, done)
    if not ubf.lines:
        return None
    out_file.parent.mkdir(parents=True, exist_ok=True)
    Stage5Assembler().process(ubf, out_file)
    return out_file


def _assemble_chapter_audio(user_id: str, book_id: str, chapter_id: int) -> Path | None:
    """Собирает WAV одной главы (строки с chapter_id) и возвращает путь. None если не все строки главы готовы."""
    key = (user_id, book_id)
    with _lock:
        state = _book_states.get(key)
        if not state:
            return None
        lines_data = state.get("lines") or []
        done = state.get("done") or {}
    chapter_lines = [t for t in lines_data if (t.get("chapter_id") or 1) == chapter_id]
    if not chapter_lines:
        return None
    line_ids = [t["line_id"] for t in chapter_lines]
    if not all(lid in done for lid in line_ids):
        return None
    book_dir = STORAGE_ROOT / "books" / user_id / book_id
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    out_file = chapters_dir / f"chapter_{chapter_id:03d}.wav"
    ubf = _build_ubf_from_state(chapter_lines, done)
    if not ubf.lines:
        return None
    Stage5Assembler().process(ubf, out_file)
    return out_file


# --- Роутер для /books ---
from api.routes.books import _read_book_title

books_router = APIRouter()
_PROJECT_ID_FILE = ".project_id"


@books_router.get("")
def list_books(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    project_id: str | None = None,
):
    """GET /books?project_id=... — список книг пользователя; при указании project_id только книги этого проекта."""
    user_id = (x_user_id or "").strip() or "anonymous"
    # Без project_id не возвращаем книги — иначе показывались бы книги всех проектов
    pid = (project_id or "").strip()
    # #region agent log
    try:
        import json
        _log = {"sessionId": "9376b5", "hypothesisId": "listbooks-core", "location": "app_pipeline.py:list_books", "message": "Core list_books entry", "data": {"user_id": user_id[:8], "project_id": (pid or "")[:8] if pid else None}, "timestamp": int(__import__("time").time() * 1000)}
        _f = open("debug-9376b5.log", "a", encoding="utf-8")
        _f.write(json.dumps(_log, ensure_ascii=False) + "\n")
        _f.close()
    except Exception:
        pass
    # #endregion
    if not pid:
        return []
    base = STORAGE_ROOT / "books" / user_id
    if not base.exists():
        return []
    result = []
    for candidate in sorted(base.iterdir()):
        if not candidate.is_dir():
            continue
        try:
            (base / candidate.name).resolve().relative_to(base.resolve())
        except ValueError:
            continue
        book_id = candidate.name
        pid_file = base / book_id / _PROJECT_ID_FILE
        if not pid_file.exists():
            continue
        try:
            if pid_file.read_text(encoding="utf-8").strip() != pid:
                continue
        except Exception:
            continue
        with _lock:
            state = _book_states.get((user_id, book_id))
        status = "uploaded"
        final_audio_path = None
        fp = STORAGE_ROOT / "books" / user_id / book_id / "final.wav"
        if state:
            total = len(state.get("lines") or [])
            if total and len(state.get("done") or {}) >= total:
                status = "done"
            elif state.get("pending"):
                status = "processing"
        # final.wav на диске — показываем даже при потере state (перезапуск Core)
        if fp.exists():
            final_audio_path = str(fp)
            if status == "uploaded":
                status = "done"
        book_dir = STORAGE_ROOT / "books" / user_id / book_id
        result.append({
            "id": book_id,
            "title": _read_book_title(book_dir),
            "status": status,
            "created_at": "",
            "final_audio_path": final_audio_path,
        })
    # #region agent log
    try:
        import json
        _log2 = {"sessionId": "9376b5", "hypothesisId": "listbooks-core", "location": "app_pipeline.py:list_books", "message": "Core list_books result", "data": {"count": len(result), "user_id": user_id[:8], "project_id": (pid or "")[:8] if pid else None}, "timestamp": int(__import__("time").time() * 1000)}
        _f2 = open("debug-9376b5.log", "a", encoding="utf-8")
        _f2.write(json.dumps(_log2, ensure_ascii=False) + "\n")
        _f2.close()
    except Exception:
        pass
    # #endregion
    return result


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
    final_path = STORAGE_ROOT / "books" / user_id / book_id / "final.wav"
    if state:
        total_lines = len(state.get("lines") or [])
        if total_lines and len(state.get("done") or {}) >= total_lines:
            status = "done"
        elif state.get("pending"):
            status = "processing"
    if final_path.exists():
        final_audio_path = str(final_path)
        if status == "uploaded":
            status = "done"
    book_dir = STORAGE_ROOT / "books" / user_id / book_id
    return {
        "id": book_id,
        "title": _read_book_title(book_dir),
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
        return {"stage": "idle", "progress": 0, "total_lines": 0, "tts_done": 0, "chapters_ready": []}
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
    # Номера глав, у которых все строки в done
    chapter_line_ids: dict[int, list[int]] = defaultdict(list)
    for t in lines:
        ch = t.get("chapter_id") or 1
        chapter_line_ids[ch].append(t["line_id"])
    chapters_ready = [
        ch for ch in sorted(chapter_line_ids)
        if all(lid in done for lid in chapter_line_ids[ch])
    ]
    return {
        "stage": stage,
        "progress": progress,
        "total_lines": total,
        "tts_done": tts_done,
        "chapters_ready": chapters_ready,
    }


@books_router.get("/{book_id}/chapters/{chapter_num}")
def get_book_chapter_audio(
    book_id: str,
    chapter_num: int,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """GET /books/:id/chapters/:num — отдать WAV главы. Если файла нет и глава полная — собираем по запросу."""
    user_id = (x_user_id or "").strip() or "anonymous"
    if not _book_dir(user_id, book_id):
        raise HTTPException(status_code=404, detail="Book not found")
    book_dir = STORAGE_ROOT / "books" / user_id / book_id
    chapters_dir = book_dir / "chapters"
    chapter_file = chapters_dir / f"chapter_{chapter_num:03d}.wav"
    if chapter_file.exists():
        return FileResponse(
            chapter_file,
            media_type="audio/wav",
            filename=chapter_file.name,
        )
    path = _assemble_chapter_audio(user_id, book_id, chapter_num)
    if path and path.exists():
        return FileResponse(
            path,
            media_type="audio/wav",
            filename=path.name,
        )
    raise HTTPException(status_code=404, detail="Chapter not ready or not found")


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
        # Fallback: если state потерян (перезапуск Core), отдаём существующий final.wav
        path = STORAGE_ROOT / "books" / user_id / book_id / "final.wav"
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

AUDIOBOOKS_ROOT = STORAGE_ROOT / "audiobooks"


def _stage4_preview_url() -> str:
    """Base URL stage4 для вызова /preview (env APP_STAGE4_URL или STAGE4_URL)."""
    return (os.environ.get("APP_STAGE4_URL") or os.environ.get("STAGE4_URL") or "http://localhost:8001").strip().rstrip("/")


@internal_router.post("/preview-by-speakers")
def post_preview_by_speakers(
    body: dict = Body(default_factory=dict),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    POST /internal/preview-by-speakers — превью по спикерам (3 фрагмента: narrator, male, female).
    Запускает Stage1 + Stage2 + постобработку по 100 символам, выбирает по одной реплике narrator, male, female
    (первые по порядку), вызывает TTS (stage4), возвращает три аудио URI.
    Тело: book_id, voice_ids?, speaker_settings? (tempo, pitch по ролям), tts_engine?.
    Ответ: { narrator: { audio_uri }, male: { audio_uri }, female: { audio_uri } } (или { error } при сбое).
    """
    user_id = (x_user_id or "").strip() or (body or {}).get("user_id") or "anonymous"
    book_id = (body or {}).get("book_id")
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id is required")
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
        post_chunk_process(ubf)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline stage1+post_chunk failed: {e!s}") from e

    # Первые по порядку реплики narrator, male, female
    picked = {}
    for line in sorted(ubf.lines, key=lambda l: l.idx):
        role = line.speaker or "narrator"
        if role not in picked and (line.original or "").strip():
            picked[role] = line
        if len(picked) >= 3:
            break
    for role in ("narrator", "male", "female"):
        if role not in picked:
            picked[role] = None

    config = _audio_settings.get("config") or {}
    voice_ids = (body or {}).get("voice_ids") or config.get("voice_ids") or {}
    if not isinstance(voice_ids, dict):
        voice_ids = {}
    effective_voice_ids = {r: str(voice_ids[r]) for r in ("narrator", "male", "female") if voice_ids.get(r)}
    speaker_settings = (body or {}).get("speaker_settings")
    if not isinstance(speaker_settings, dict):
        _, _, prev_ss = _load_book_voice_config(book_dir)
        speaker_settings = prev_ss or {r: {"tempo": 1.0, "pitch": 0.0} for r in ("narrator", "male", "female")}
    tts_engine = (body or {}).get("tts_engine") or config.get("tts_engine") or "qwen3"

    payload = {
        "user_id": user_id,
        "book_id": book_id,
        "voice_ids": effective_voice_ids,
        "speaker_settings": speaker_settings,
        "tts_engine": tts_engine,
    }
    for role in ("narrator", "male", "female"):
        line = picked.get(role)
        if line and (line.original or "").strip():
            voice = effective_voice_ids.get(role) or role
            raw = (line.original or "").strip()[:500]
            text_for_payload = (getattr(line, "text_for_tts", None) or "").strip()[:500]
            payload[role] = {
                "text": text_for_payload if text_for_payload else normalize_text_for_tts(raw),
                "speaker": voice,
                "speaker_wav_path": get_voice_path(voice, user_id=user_id),
            }
        else:
            payload[role] = {"text": " ", "speaker": role}

    try:
        r = requests.post(f"{_stage4_preview_url()}/preview", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        resp = getattr(e, "response", None)
        body_preview = (resp.text[:500] if resp and getattr(resp, "text", None) else None) or ""
        _log.warning(
            "stage4 preview request failed: %s; status=%s body=%s",
            e, getattr(resp, "status_code", None), body_preview,
        )
        raise HTTPException(status_code=502, detail=f"Stage4 preview failed: {e!s}") from e

    # Сплющиваем в URL для клиента: narrator/male/female -> "/internal/storage?path=books/..."
    result = {}
    warnings = []
    for role in ("narrator", "male", "female"):
        item = data.get(role)
        if isinstance(item, dict) and item.get("audio_uri") and "error" not in item:
            result[role] = f"/internal/storage?path={quote(item['audio_uri'])}"
        elif isinstance(item, dict) and item.get("error"):
            err_msg = item["error"]
            _log.warning("preview %s error: %s", role, err_msg)
            warnings.append(f"{role}: {err_msg}")
    if warnings:
        result["warnings"] = warnings
    return result


@internal_router.get("/storage")
def get_internal_storage(path: str = ""):
    """
    GET /internal/storage?path=books/user_id/book_id/preview_narrator.wav — отдать файл из STORAGE_ROOT.
    Нужно для проигрывания превью в браузере при доступе через proxy.
    """
    raw = (path or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="path is required")
    rel = unquote(raw)
    if ".." in rel or rel.startswith("/") or "\\" in rel:
        raise HTTPException(status_code=400, detail="Invalid path")
    full = STORAGE_ROOT / rel
    if not full.is_file() or not str(full.resolve()).startswith(str(STORAGE_ROOT.resolve())):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        full,
        media_type="audio/wav" if rel.endswith(".wav") else "application/octet-stream",
        filename=full.name,
    )


def _sanitize_folder_name(name: str) -> str:
    """Имя папки без недопустимых символов; пробелы в подчёркивания."""
    s = (name or "").strip() or "book"
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:200] or "book"


@internal_router.post("/finalize-audiobook")
def post_finalize_audiobook(
    body: dict = Body(default_factory=dict),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    POST /internal/finalize-audiobook — копирует финальное аудио в storage/audiobooks/<user_id>/<название_книги>/,
    затем удаляет рабочую папку storage/books/<user_id>/<book_id>/.
    Тело: user_id, book_id, project_title (опционально). Возвращает folder (имя папки для стриминга).
    """
    user_id = (x_user_id or "").strip() or (body or {}).get("user_id") or "anonymous"
    book_id = (body or {}).get("book_id")
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id is required")
    book_dir = _book_dir(user_id, book_id)
    if not book_dir:
        raise HTTPException(status_code=404, detail="Book not found")

    title = (body or {}).get("project_title") or _read_book_title(book_dir)
    folder_name = _sanitize_folder_name(title)
    out_dir = AUDIOBOOKS_ROOT / user_id / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    final_wav = book_dir / "final.wav"
    copied = []
    if final_wav.exists():
        dest = out_dir / "full.wav"
        shutil.copy2(final_wav, dest)
        copied.append(str(dest))

    chapters_dir = book_dir / "chapters"
    if chapters_dir.exists():
        for f in sorted(chapters_dir.glob("*.wav")):
            dest = out_dir / f.name
            shutil.copy2(f, dest)
            copied.append(str(dest))

    if not copied:
        raise HTTPException(
            status_code=404,
            detail="No final.wav or chapter WAVs found. Finish narration first.",
        )

    try:
        shutil.rmtree(book_dir)
    except OSError as e:
        # Копия уже в audiobooks — логируем, но не падаем
        import logging
        logging.getLogger(__name__).warning("Failed to remove book_dir %s: %s", book_dir, e)

    return {"path": str(out_dir), "files": copied, "folder": folder_name}


@internal_router.get("/audiobooks/stream")
def get_audiobook_stream(
    folder: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    GET /internal/audiobooks/stream?folder=<name> — отдать full.wav из storage/audiobooks/<user_id>/<folder>/.
    Требуется заголовок X-User-Id. Имя folder должно совпадать с результатом _sanitize_folder_name.
    """
    user_id = (x_user_id or "").strip() or "anonymous"
    safe_folder = _sanitize_folder_name(folder)
    if safe_folder != folder:
        raise HTTPException(status_code=400, detail="Invalid folder name")
    file_path = AUDIOBOOKS_ROOT / user_id / folder / "full.wav"
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audiobook file not found")
    return FileResponse(
        file_path,
        media_type="audio/wav",
        filename="full.wav",
    )


def _process_book_stage4_post_stage3(
    user_id: str,
    book_id: str,
    body: dict,
    book_dir: Path,
    ubf: UserBookFormat,
    voice_ids: dict,
    tts_engine: str,
    max_tasks: int,
) -> dict:
    """Выполняет нормализацию, сохранение, сбор lines_data и постановку в очередь. Вызывается из потока."""
    # Нормализация text_for_tts
    _log.info("process-book-stage4: post-Stage3 step 1 — normalizing text_for_tts")
    for line in ubf.lines:
        if not getattr(line, "text_for_tts", None) and (line.original or "").strip():
            line.text_for_tts = normalize_text_for_tts((line.original or "").strip())
    _log.info("process-book-stage4: post-Stage3 step 2 — saving text_with_roles")
    _save_processed_text_with_roles(book_dir, ubf)

    prev_voice_ids_cfg, prev_tts_engine, prev_speaker_settings = _load_book_voice_config(book_dir)
    body_ss = (body or {}).get("speaker_settings")
    if isinstance(body_ss, dict):
        speaker_settings = {}
        for r in ("narrator", "male", "female"):
            x = body_ss.get(r)
            speaker_settings[r] = (
                {"tempo": float(x.get("tempo", 1.0)), "pitch": float(x.get("pitch", 0.0))}
                if isinstance(x, dict) else {"tempo": 1.0, "pitch": 0.0}
            )
    else:
        speaker_settings = prev_speaker_settings or {r: {"tempo": 1.0, "pitch": 0.0} for r in ("narrator", "male", "female")}

    lines_data = []
    config_voice_ids = (_audio_settings.get("config") or {}).get("voice_ids") or {}
    effective_voice_ids = {}
    for role in ("narrator", "male", "female"):
        if isinstance(voice_ids, dict) and voice_ids.get(role):
            effective_voice_ids[role] = str(voice_ids[role])
        elif isinstance(config_voice_ids, dict) and config_voice_ids.get(role):
            effective_voice_ids[role] = str(config_voice_ids[role])
    effective_voice_ids = dict(effective_voice_ids)
    _log.info("process-book-stage4: effective_voice_ids=%s max_tasks=%s", effective_voice_ids, max_tasks)

    skipped_empty = 0
    skipped_empty_text = 0
    sorted_lines = sorted(ubf.lines, key=lambda l: l.idx)
    sample_orig_lens = [(l.idx, len((l.original or "").strip()), bool((l.original or "").strip())) for l in sorted_lines[:3]]
    _log.info("process-book-stage4: building lines_data ubf.lines=%s sample_orig_len=%s", len(ubf.lines), sample_orig_lens)
    for line in sorted_lines:
        if max_tasks and len(lines_data) >= max_tasks:
            break
        if not (line.original or "").strip():
            skipped_empty += 1
            continue
        text_for_task = (
            line.text_for_tts if getattr(line, "text_for_tts", None)
            else normalize_text_for_tts((line.original or "").strip())
        )
        if not (text_for_task or "").strip():
            skipped_empty_text += 1
            continue
        role = line.speaker or "narrator"
        voice_for_tts = effective_voice_ids.get(role) or role
        speaker_wav_path = get_voice_path(voice_for_tts, user_id=user_id)
        emotion_for_tts = _speaker_settings_to_emotion(speaker_settings, role)
        parts = [text_for_task.strip()]
        if tts_engine == "xtts2" and len(parts[0]) > 100:
            parts = _split_text_for_xtts(parts[0], max_len=100)
        for pi, part in enumerate(parts, start=1):
            if not part:
                continue
            # Чтобы сохранить порядок, делаем новый line_id для частей: base*1000 + part_index
            line_id = line.idx * 1000 + pi if len(parts) > 1 else line.idx
            lines_data.append({
                "line_id": line_id,
                "text": part.strip(),
                "voice": voice_for_tts,
                "role": role,
                "emotion": emotion_for_tts,
                "audio_config": {"voice_ids": effective_voice_ids} if effective_voice_ids else None,
                "chapter_id": (line.chapter_id if line.chapter_id is not None else 1),
                "tts_engine": tts_engine,
                "speaker_wav_path": speaker_wav_path,
                "is_chapter_header": getattr(line, "is_chapter_header", False) and pi == 1,
                "type": line.type or "narrator",
            })

    _log.info(
        "process-book-stage4: ubf.lines=%s lines_data=%s skipped_empty=%s skipped_empty_text=%s",
        len(ubf.lines), len(lines_data), skipped_empty, skipped_empty_text,
    )

    force_re_synthesize = (body or {}).get("force") is True
    lines_dir = book_dir / "lines"
    lines_dir.mkdir(parents=True, exist_ok=True)
    prev_voice_ids = prev_voice_ids_cfg or {}
    tts_engine_unchanged = (prev_tts_engine or "qwen3") == tts_engine
    done: dict[int, str] = {}
    pending_ids: list[int] = []
    for t in lines_data:
        line_id = t["line_id"]
        role = t.get("role", "narrator")
        existing_path = lines_dir / f"line_{line_id}.wav"
        voice_unchanged = prev_voice_ids.get(role) == effective_voice_ids.get(role)
        reuse = not force_re_synthesize and existing_path.exists() and voice_unchanged and tts_engine_unchanged
        if reuse:
            done[line_id] = str(existing_path)
        else:
            if existing_path.exists():
                try:
                    existing_path.unlink()
                except OSError:
                    pass
            pending_ids.append(line_id)
    pending = deque(pending_ids)
    _log.info("process-book-stage4: reuse check done → done=%s pending=%s", len(done), len(pending_ids))
    _save_book_voice_config(book_dir, effective_voice_ids, tts_engine, speaker_settings)
    if pending:
        final_wav = book_dir / "final.wav"
        if final_wav.exists():
            try:
                final_wav.unlink()
            except OSError:
                pass

    key = (user_id, book_id)
    _log.info("process-book-stage4: before lock key=%s pending_len=%s will_enqueue=%s", key, len(pending), bool(pending))
    with _lock:
        _book_states[key] = {
            "lines": lines_data,
            "pending": pending,
            "done": done,
            "stop_requested": False,
            "voice_ids": effective_voice_ids,
            "tts_engine": tts_engine,
        }
        enqueued = False
        if pending:
            try:
                _pending_books.remove(key)
            except ValueError:
                pass
            _pending_books.append(key)
            enqueued = True
        _pending_books_len = len(_pending_books)
    _log.info("process-book-stage4: after lock enqueued=%s queue_len=%s", enqueued, _pending_books_len)

    final_path = None
    if not pending and done:
        final_path = _assemble_final_audio(user_id, book_id)
    remaining = len(pending)
    _log.info(
        "process-book-stage4 outcome: book_id=%s pending=%s done=%s enqueued=%s queue_len=%s",
        book_id, remaining, len(done), enqueued, _pending_books_len,
    )
    return {
        "book_id": book_id,
        "processed_tasks": len(done),
        "remaining_tasks": remaining,
        "book_status": "done" if (not pending and done) else "processing",
        "final_audio_path": str(final_path) if final_path else None,
        "stopped": False,
        "all_lines_done": bool(remaining == 0 and done),
    }


@internal_router.post("/process-book-stage4")
def post_process_book_stage4(
    body: dict = Body(default_factory=dict),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """
    POST /internal/process-book-stage4 — запуск пайплайна: stage1–3, формирование очереди для stage4 (TTS).
    Body: book_id, max_tasks?, voice_ids?, tts_engine?, speaker_settings?, force? (true = все строки в pending).
    В логах: «process-book-stage4 outcome: … pending=… enqueued=…» — по нему видно, ушло ли в stage4.
    """
    user_id = (x_user_id or "").strip() or "anonymous"
    book_id = (body or {}).get("book_id")
    body_tts_engine = (body or {}).get("tts_engine")
    _log.info(
        "process-book-stage4 request book_id=%s user_id=%s body.tts_engine=%s",
        book_id, user_id, body_tts_engine,
    )
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id is required")
    max_tasks = int((body or {}).get("max_tasks", 0))
    voice_ids = (body or {}).get("voice_ids") or {}
    if isinstance(voice_ids, dict):
        voice_ids = {k: v for k, v in voice_ids.items() if v}
    else:
        voice_ids = {}
    config = _audio_settings.get("config") or {}
    tts_engine = (body or {}).get("tts_engine") or config.get("tts_engine") or "qwen3"
    if tts_engine not in ("qwen3", "xtts2"):
        tts_engine = "qwen3"
    book_dir = _book_dir(user_id, book_id)
    if not book_dir:
        raise HTTPException(status_code=404, detail="Book not found")
    txt_path = _find_book_txt(book_dir)
    if not txt_path:
        raise HTTPException(status_code=404, detail="No .txt file in book original/")
    _log.info("process-book-stage4: book_dir=%s txt_path=%s", book_dir, txt_path)

    try:
        parser = StructuralParser(split_for_xtts=True)
        ubf = parser.parse_file(txt_path)
        _log.info("process-book-stage4: Stage1 done ubf.lines=%s", len(ubf.lines))
        SpeakerResolver().process(ubf)
        post_chunk_process(ubf)  # группировка по спикеру/chapter_id, резание ~100 символов
        _log.info("process-book-stage4: Stage2+post_chunk done ubf.lines=%s", len(ubf.lines))
        EmotionResolver().process(ubf)
        _log.info("process-book-stage4: Stage3 done ubf.lines=%s", len(ubf.lines))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline stage1-3 failed: {e!s}",
        ) from e

    # Формирование очереди в фоновом потоке: при обрыве соединения клиентом поток всё равно завершит работу.
    result_ref: list[dict | None] = [None]
    err_ref: list[BaseException | None] = [None]

    def run_post_stage3() -> None:
        try:
            result_ref[0] = _process_book_stage4_post_stage3(
                user_id=user_id,
                book_id=book_id,
                body=body or {},
                book_dir=book_dir,
                ubf=ubf,
                voice_ids=voice_ids,
                tts_engine=tts_engine,
                max_tasks=max_tasks,
            )
        except BaseException as e:
            err_ref[0] = e
            _log.exception("process-book-stage4: post-Stage3 thread failed: %s", e)

    thread = threading.Thread(target=run_post_stage3, daemon=False)
    thread.start()
    thread.join(timeout=300.0)

    if err_ref[0]:
        raise HTTPException(status_code=500, detail=f"Post-Stage3 failed: {err_ref[0]!s}") from err_ref[0]
    if result_ref[0] is not None:
        return result_ref[0]
    # Таймаут или обрыв — очередь могла уже заполниться в потоке
    _log.warning("process-book-stage4: post-Stage3 thread did not finish in time or client disconnected")
    return {
        "book_id": book_id,
        "processed_tasks": 0,
        "remaining_tasks": -1,
        "book_status": "processing",
        "final_audio_path": None,
        "stopped": False,
        "all_lines_done": False,
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
            result = {
                "task_id": task_id,
                "user_id": user_id,
                "book_id": book_id,
                "line_id": line_id,
                "text": task["text"],
                "voice": task["voice"],
                "emotion": task.get("emotion") or {},
                "audio_config": task.get("audio_config"),
                "tts_engine": task.get("tts_engine", "qwen3"),
            }
            if task.get("speaker_wav_path"):
                result["speaker_wav_path"] = task["speaker_wav_path"]
            _log.info(
                "tts-next: issued task book_id=%s line_id=%s tts_engine=%s",
                result.get("book_id"), result.get("line_id"), result.get("tts_engine", "qwen3"),
            )
            return result
    _log.info(
        "tts-next: queue empty (no pending books/tasks), returning 404. queue_len=%s keys=%s",
        len(_pending_books), list(_pending_books)[:5],
    )
    raise HTTPException(status_code=404, detail="No pending tasks")


@internal_router.post("/tts-next-batch")
def post_tts_next_batch(count: int = 3):
    """
    POST /internal/tts-next-batch?count=N — выдать до N задач из очереди (одна книга, один speaker).
    Возвращает 404, если очереди пусты.
    """
    global _last_leased_batch
    count = max(1, min(count, 16))
    tasks = []
    with _lock:
        while _pending_books and len(tasks) < count:
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
            first_voice = tasks[0].get("voice") if tasks else None
            if tasks and first_voice and task.get("voice") != first_voice:
                pending.appendleft(line_id)
                break
            task_data = {
                "task_id": task_id,
                "user_id": user_id,
                "book_id": book_id,
                "line_id": line_id,
                "text": task["text"],
                "voice": task["voice"],
                "emotion": task.get("emotion") or {},
                "audio_config": task.get("audio_config"),
                "tts_engine": task.get("tts_engine", "qwen3"),
            }
            if task.get("speaker_wav_path"):
                task_data["speaker_wav_path"] = task["speaker_wav_path"]
            tasks.append(task_data)
    if not tasks:
        raise HTTPException(status_code=404, detail="No pending tasks")
    _log.info(
        "tts-next-batch: issued %s tasks book_id=%s tts_engine=%s",
        len(tasks), tasks[0].get("book_id"), tasks[0].get("tts_engine", "qwen3"),
    )
    _last_leased_batch = [{"user_id": t["user_id"], "book_id": t["book_id"], "line_id": t["line_id"]} for t in tasks]
    return {"tasks": tasks}


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


@internal_router.post("/tts-complete-batch")
def post_tts_complete_batch(body: dict = Body(default_factory=dict)):
    """
    POST /internal/tts-complete-batch — отметить несколько строк озвученными.
    Тело: {"results": [{"line_id": x, "audio_path": "..."}, ...], "user_id": "...", "book_id": "..."}.
    user_id и book_id обязательны (все задачи из одной книги).
    """
    global _last_leased_batch
    data = body or {}
    results = data.get("results") or []
    if not results:
        raise HTTPException(status_code=400, detail="results array required")
    user_id = data.get("user_id")
    book_id = data.get("book_id")
    if not user_id or not book_id:
        leased = _last_leased_batch
        if leased and len(leased) >= len(results):
            user_id = leased[0].get("user_id")
            book_id = leased[0].get("book_id")
        if not user_id or not book_id:
            raise HTTPException(status_code=400, detail="user_id and book_id required")
    key = (user_id, book_id)
    with _lock:
        state = _book_states.get(key)
        if not state:
            raise HTTPException(status_code=404, detail="Book state not found")
        for r in results:
            lid = r.get("line_id")
            path = r.get("audio_path")
            if lid is not None and path:
                state.setdefault("done", {})[lid] = path
    _last_leased_batch = None
    return {"processed": len(results), "book_id": book_id}


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
