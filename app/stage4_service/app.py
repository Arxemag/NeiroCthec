from __future__ import annotations

import logging
import os
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(name)s: %(message)s",
)
import tempfile
import threading
import time
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException

logger = logging.getLogger("stage4")

from stage4_service.schemas import TTSRequest, TTSResponse, TTSStatus
from stage4_service.storage import LocalObjectStorage, maybe_get_s3_storage
import shutil
from stage4_service.synth import ExternalHTTPSynthesizer, MockSynthesizer

app = FastAPI(title="Stage4 TTS Worker")


def _build_synth(mode: str, base_url: str, timeout_sec: int):
    if mode == "external":
        return ExternalHTTPSynthesizer(base_url=base_url, timeout_sec=timeout_sec)
    return MockSynthesizer()


def _get_synthesizers():
    """Два TTS-сервиса: Qwen3 (8020) и XTTS2 (8021). По задаче выбираем по tts_engine."""
    mode = os.getenv("STAGE4_SYNTH_MODE", "mock").strip().lower()
    timeout = int(os.getenv("EXTERNAL_TTS_TIMEOUT_SEC", "60"))
    timeout_xtts = int(os.getenv("EXTERNAL_TTS_XTTS_TIMEOUT_SEC", str(timeout)))
    url_qwen3 = os.getenv("EXTERNAL_TTS_QWEN3_URL", os.getenv("EXTERNAL_TTS_URL", "http://host.docker.internal:8020")).strip().rstrip("/")
    url_xtts = os.getenv("EXTERNAL_TTS_XTTS_URL", "http://tts-xtts:8021").strip().rstrip("/")
    return {
        "qwen3": _build_synth(mode, url_qwen3, timeout),
        "xtts2": _build_synth(mode, url_xtts, timeout_xtts),
    }


_synthesizers = _get_synthesizers()


def _synth_for_engine(tts_engine: str | None):
    e = (tts_engine or "qwen3").strip().lower()
    return _synthesizers.get(e) or _synthesizers["qwen3"]
storage = LocalObjectStorage()
s3_storage = maybe_get_s3_storage()
# Без пробелов и без завершающего слэша, иначе получится /internal%20/tts-next и 404
core_internal_url = (os.getenv("CORE_INTERNAL_URL", "http://core:8000/internal") or "").strip().rstrip("/")


def _storage_key_for_task(*, user_id: str, book_id: str, line_id: int, task_id: str, local_audio_uri: str) -> str:
    """
    В target storageKey для артефактов адресуется по (clientId, taskId).
    Для текущего пайплайна core assembly по-прежнему читает локальные files,
    поэтому core /tts-complete получает local_audio_uri, а TaskRegistry — s3 key.
    """
    storage_key = local_audio_uri
    if not s3_storage:
        return storage_key
    try:
        key = s3_storage.key_for_task(user_id, task_id)
        local_path = storage.path_for_line(user_id, book_id, line_id)
        s3_storage.upload_file(key=key, file_path=local_path)
        storage_key = key
    except Exception as e:
        logger.warning("S3 upload failed taskId=%s: %s", task_id, e)
    return storage_key

# TaskRegistry (NestJS) — опциональная интеграция
_task_registry_api_url = (os.getenv("TASK_REGISTRY_API_URL") or "").strip().rstrip("/")
_task_registry_internal_token = os.getenv("TASK_REGISTRY_INTERNAL_TOKEN") or ""
_task_registry_headers: dict[str, str] = (
    {"X-Internal-Token": _task_registry_internal_token} if _task_registry_internal_token else {}
)


def _task_registry_complete(*, task_id: str, storage_key: str, duration_ms: float | None = None) -> None:
    if not _task_registry_api_url:
        return
    try:
        payload: dict = {"storageKey": storage_key}
        if duration_ms is not None:
            payload["durationMs"] = duration_ms
        requests.post(
            f"{_task_registry_api_url}/internal/task-registry/tasks/{task_id}/complete",
            json=payload,
            headers=_task_registry_headers,
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        logger.warning("TaskRegistry complete failed taskId=%s: %s", task_id, e)


def _task_registry_fail(*, task_id: str, error_message: str) -> None:
    if not _task_registry_api_url:
        return
    try:
        requests.post(
            f"{_task_registry_api_url}/internal/task-registry/tasks/{task_id}/fail",
            json={"errorMessage": error_message},
            headers=_task_registry_headers,
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        logger.warning("TaskRegistry fail failed taskId=%s: %s", task_id, e)

# Redis Stream queue mode (Core → Stage4)
_TTS_USE_REDIS_QUEUE = os.getenv("TTS_USE_REDIS_QUEUE", "").strip().lower() in {"1", "true", "yes", "on"}
_TTS_RENDER_STREAM = (os.getenv("TTS_RENDER_STREAM") or "tts.render.v1").strip()
_TTS_REDIS_URL = (os.getenv("REDIS_URL") or "").strip()
_TTS_STAGE4_CONSUMER_GROUP = (os.getenv("TTS_STAGE4_CONSUMER_GROUP") or "stage4_worker").strip()
_TTS_STAGE4_CONSUMER_NAME = (os.getenv("TTS_STAGE4_CONSUMER_NAME") or "stage4_1").strip()
_TTS_DLQ_STREAM = (os.getenv("TTS_DLQ_STREAM") or f"{_TTS_RENDER_STREAM}.dlq").strip()

_redis_client = None
_redis_lock = threading.Lock()
_consumer_group_ready = False


def _get_redis_client():
    global _redis_client, _consumer_group_ready
    if not _TTS_USE_REDIS_QUEUE:
        return None
    if not _TTS_REDIS_URL:
        return None
    with _redis_lock:
        if _redis_client is None:
            try:
                import redis  # type: ignore

                _redis_client = redis.Redis.from_url(_TTS_REDIS_URL)
            except Exception as e:
                logger.warning("Redis client init failed: %s", e)
                _redis_client = None
                _consumer_group_ready = False
    return _redis_client


def _ensure_consumer_group(r) -> None:
    global _consumer_group_ready
    if _consumer_group_ready or not r:
        return
    try:
        # id='$' и mkstream=True — создаст стрим, если его ещё нет, и не переобработает старые сообщения
        r.xgroup_create(_TTS_RENDER_STREAM, _TTS_STAGE4_CONSUMER_GROUP, id="$", mkstream=True)
    except Exception as e:
        # BUSYGROUP — нормальная ситуация (уже создана группа)
        msg = str(e).lower()
        if "busygrou" not in msg:
            logger.warning("Redis xgroup_create failed: %s", e)
    _consumer_group_ready = True


def _publish_to_dlq(*, msg_id: str | None, payload: dict, error_message: str) -> None:
    """Отправляет проблемное сообщение в DLQ stream для последующего анализа/replay."""
    r = _get_redis_client()
    if not r:
        return
    try:
        safe_payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fields: dict[str, str] = {
            "payload": safe_payload_json,
            "errorMessage": str(error_message or "unknown"),
        }
        if msg_id:
            fields["sourceMsgId"] = str(msg_id)
        r.xadd(_TTS_DLQ_STREAM, fields)
    except Exception as e:
        logger.warning("DLQ xadd failed: %s", e)


def _read_one_task_from_stream(timeout_ms: int = 1000) -> tuple[str, dict] | None:
    """Возвращает (message_id, task_payload) или None если нет сообщений."""
    r = _get_redis_client()
    if not r:
        return None
    _ensure_consumer_group(r)
    try:
        res = r.xreadgroup(
            _TTS_STAGE4_CONSUMER_GROUP,
            _TTS_STAGE4_CONSUMER_NAME,
            {_TTS_RENDER_STREAM: ">"},
            count=1,
            block=timeout_ms,
        )
    except Exception as e:
        logger.warning("Redis xreadgroup failed: %s", e)
        return None
    if not res:
        return None
    # res: [(stream_name, [(msg_id, {field: value})...])]
    _, entries = res[0]
    if not entries:
        return None
    msg_id, fields = entries[0]
    raw_payload = fields.get("payload") or fields.get(b"payload")
    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode("utf-8", errors="replace")
    if not isinstance(raw_payload, str):
        return None
    task_payload = json.loads(raw_payload)
    return str(msg_id), task_payload

# Счётчик опросов с пустой очередью — раз в ~30 сек пишем в лог
_empty_poll_count = 0


@app.get("/health")
def health():
    return {"status": "ok"}


def _is_connection_error(exc: BaseException) -> bool:
    """Проверка: ошибка доступа к сервису (DNS, connection refused, timeout)."""
    err_str = str(exc).lower()
    if "nameresolutionerror" in err_str or "failed to resolve" in err_str or "no address associated" in err_str:
        return True
    if "connectionrefused" in err_str or "connection refused" in err_str:
        return True
    if "max retries exceeded" in err_str or "timeout" in err_str:
        return True
    return False


@app.post("/tts", response_model=TTSResponse)
def tts(request: TTSRequest):
    engine = (getattr(request, "tts_engine", None) or "qwen3").strip().lower()
    synth = _synth_for_engine(engine)
    url_xtts = os.getenv("EXTERNAL_TTS_XTTS_URL", "http://tts-xtts:8021").strip().rstrip("/")
    logger.info(
        "TTS engine=%s book_id=%s line_id=%s (xtts_url=%s when engine=xtts2)",
        engine, request.book_id, request.line_id, url_xtts if engine == "xtts2" else "n/a",
    )
    try:
        relative = Path(request.user_id) / request.book_id / f"line_{request.line_id}.wav"
        tmp_path = Path(tempfile.gettempdir()) / relative
        duration_ms = synth.synthesize(request=request, output_path=tmp_path)
        target = storage.path_for_line(request.user_id, request.book_id, request.line_id)
        shutil.copyfile(tmp_path, target)
        audio_uri = storage.uri_for_line(request.user_id, request.book_id, request.line_id)
        return TTSResponse(task_id=request.task_id, status=TTSStatus.DONE, audio_uri=audio_uri, duration_ms=duration_ms)
    except Exception as exc:
        # Если Qwen3 недоступен (контейнер не запущен и т.д.) — повторить через XTTS2
        if engine == "qwen3" and _is_connection_error(exc):
            logger.warning(
                "Qwen3 unreachable (%s), falling back to XTTS2 for book_id=%s line_id=%s",
                exc, request.book_id, request.line_id,
            )
            synth_xtts = _synth_for_engine("xtts2")
            try:
                relative = Path(request.user_id) / request.book_id / f"line_{request.line_id}.wav"
                tmp_path = Path(tempfile.gettempdir()) / relative
                duration_ms = synth_xtts.synthesize(request=request, output_path=tmp_path)
                target = storage.path_for_line(request.user_id, request.book_id, request.line_id)
                shutil.copyfile(tmp_path, target)
                audio_uri = storage.uri_for_line(request.user_id, request.book_id, request.line_id)
                return TTSResponse(task_id=request.task_id, status=TTSStatus.DONE, audio_uri=audio_uri, duration_ms=duration_ms)
            except Exception as exc2:
                return TTSResponse(task_id=request.task_id, status=TTSStatus.ERROR, error=str(exc2))
        return TTSResponse(task_id=request.task_id, status=TTSStatus.ERROR, error=str(exc))


def _preview_one(
    user_id: str,
    book_id: str,
    role: str,
    text: str,
    speaker: str,
    emotion: dict,
    voice_ids: dict,
    tts_engine: str,
    speaker_wav_path: str | None,
) -> dict:
    """Синтезирует один превью-фрагмент и возвращает { audio_uri } или { error }."""
    req = TTSRequest(
        task_id=f"preview_{role}",
        user_id=user_id,
        book_id=book_id,
        line_id=0,
        text=text,
        speaker=speaker,
        emotion=emotion,
        audio_config={"voice_ids": voice_ids} if voice_ids else None,
        speaker_wav_path=speaker_wav_path,
        tts_engine=tts_engine,
    )
    synth = _synth_for_engine(tts_engine or "qwen3")
    out = storage.path_for_preview(user_id, book_id, role)
    try:
        synth.synthesize(request=req, output_path=out)
        uri = storage.uri_for_preview(user_id, book_id, role)
        return {"audio_uri": uri}
    except Exception as e:
        logger.warning("Preview %s failed: %s", role, e)
        return {"error": str(e)}


@app.post("/preview")
def post_preview(body: dict | None = None):
    """
    POST /preview — синтез трёх превью по спикерам (narrator, male, female).
    Тело: user_id, book_id, narrator: { text, speaker }, male: {...}, female: {...},
    voice_ids?, speaker_settings? (tempo/pitch по ролям), tts_engine?.
    Возвращает: { narrator: { audio_uri }, male: { audio_uri }, female: { audio_uri } }.
    """
    data = body or {}
    user_id = (data.get("user_id") or "anonymous").strip()
    book_id = data.get("book_id") or ""
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id required")
    voice_ids = data.get("voice_ids") or {}
    if not isinstance(voice_ids, dict):
        voice_ids = {}
    speaker_settings = data.get("speaker_settings") or {}
    if not isinstance(speaker_settings, dict):
        speaker_settings = {}
    tts_engine = (data.get("tts_engine") or "qwen3").strip().lower()

    def emotion_for(role: str) -> dict:
        s = speaker_settings.get(role)
        if isinstance(s, dict):
            return {"tempo": float(s.get("tempo", 1.0)), "pitch": float(s.get("pitch", 0.0))}
        return {"tempo": 1.0, "pitch": 0.0}

    result = {}
    for role in ("narrator", "male", "female"):
        item = data.get(role)
        if not isinstance(item, dict):
            result[role] = {"error": "missing text/speaker"}
            continue
        text = (item.get("text") or "").strip()
        speaker = (item.get("speaker") or role).strip()
        if not text:
            result[role] = {"error": "empty text"}
            continue
        speaker_wav_path = item.get("speaker_wav_path") if isinstance(item.get("speaker_wav_path"), str) else None
        result[role] = _preview_one(
            user_id=user_id,
            book_id=book_id,
            role=role,
            text=text,
            speaker=speaker,
            emotion=emotion_for(role),
            voice_ids=voice_ids,
            tts_engine=tts_engine,
            speaker_wav_path=speaker_wav_path,
        )
    return result


@app.post("/process-next")
def process_next_task():
    lease = requests.post(f"{core_internal_url}/tts-next", timeout=20)
    if lease.status_code == 404:
        return {"status": "empty"}
    lease.raise_for_status()
    task = lease.json()

    req = TTSRequest(
        task_id=task["task_id"],
        user_id=task["user_id"],
        book_id=task["book_id"],
        line_id=task["line_id"],
        text=task["text"],
        speaker=task["voice"],
        emotion=task["emotion"],
        audio_config=task.get("audio_config"),
        speaker_wav_path=task.get("speaker_wav_path"),
        tts_engine=task.get("tts_engine", "qwen3"),
    )

    result = tts(req)
    if result.status != TTSStatus.DONE:
        raise HTTPException(status_code=500, detail=result.error or "TTS failed")

    requests.post(
        f"{core_internal_url}/tts-complete",
        json={
            "user_id": task["user_id"],
            "book_id": task["book_id"],
            "line_id": task["line_id"],
            "audio_path": result.audio_uri,
        },
        timeout=20,
    ).raise_for_status()

    return {"status": "processed", "line_id": task["line_id"], "audio_path": result.audio_uri}


def _process_one_task() -> bool:
    """Забрать задачу(и) из core, озвучить, отправить tts-complete. Возвращает True если была задача."""
    if _TTS_USE_REDIS_QUEUE:
        msg = _read_one_task_from_stream(timeout_ms=2000)
        if not msg:
            return False
        msg_id, task = msg
        t0 = time.monotonic()

        client_id = task.get("clientId") or ""
        book_id = task.get("bookId") or ""
        line_id = task.get("lineId")
        task_id = task.get("taskId") or ""
        text = task.get("text") or ""
        voice = task.get("voice") or "narrator"

        if not (client_id and book_id and isinstance(line_id, int) and task_id and text.strip()):
            logger.warning("Invalid task payload from stream: %s", task)
            r = _get_redis_client()
            if r:
                try:
                    r.xack(_TTS_RENDER_STREAM, _TTS_STAGE4_CONSUMER_GROUP, msg_id)
                except Exception:
                    pass
            return True

        req = TTSRequest(
            task_id=task_id,
            user_id=client_id,
            book_id=book_id,
            line_id=line_id,
            text=text,
            speaker=voice,
            emotion=task.get("emotion"),
            audio_config=task.get("audio_config"),
            speaker_wav_path=task.get("speaker_wav_path"),
            tts_engine=task.get("tts_engine", "qwen3"),
        )

        result = tts(req)

        # При 503 (модель ещё грузится) повторяем запрос несколько раз с паузой
        retry_on_503 = int(os.getenv("STAGE4_TTS_503_RETRIES", "5"))
        retry_delay_sec = int(os.getenv("STAGE4_TTS_503_RETRY_DELAY_SEC", "20"))
        for _ in range(retry_on_503 - 1):
            if result.status == TTSStatus.DONE:
                break
            err = result.error or ""
            if "503" not in err and "Service Unavailable" not in err:
                break
            logger.info(
                "TTS 503 (model loading?), retry in %ss book_id=%s line_id=%s",
                retry_delay_sec,
                req.book_id,
                req.line_id,
            )
            time.sleep(retry_delay_sec)
            result = tts(req)

        if result.status != TTSStatus.DONE:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "TTS failed (stream) taskId=%s clientId=%s book_id=%s line_id=%s engine=%s latencyMs=%s durationMs=%s: %s",
                req.task_id,
                client_id,
                req.book_id,
                req.line_id,
                getattr(req, "tts_engine", "qwen3"),
                elapsed_ms,
                result.duration_ms,
                result.error or "unknown",
            )
            _task_registry_fail(task_id=req.task_id, error_message=result.error or "tts_failed")
            _publish_to_dlq(
                msg_id=msg_id,
                payload=task,
                error_message=result.error or "tts_failed",
            )
            r = _get_redis_client()
            if r:
                try:
                    r.xack(_TTS_RENDER_STREAM, _TTS_STAGE4_CONSUMER_GROUP, msg_id)
                except Exception:
                    pass
            return True

        # TaskRegistry + Core завершение задачи
        local_audio_uri = result.audio_uri or ""
        task_storage_key = _storage_key_for_task(
            user_id=client_id,
            book_id=book_id,
            line_id=line_id,
            task_id=req.task_id,
            local_audio_uri=local_audio_uri,
        )
        _task_registry_complete(
            task_id=req.task_id,
            storage_key=task_storage_key,
            duration_ms=result.duration_ms,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        try:
            wav_path = storage.path_for_line(client_id, book_id, line_id)
            wav_bytes = wav_path.stat().st_size if wav_path.exists() else None
        except Exception:
            wav_bytes = None
        logger.info(
            "stage4 stream OK taskId=%s clientId=%s bookId=%s lineId=%s engine=%s latencyMs=%s bytes=%s durationMs=%s storageKey=%s",
            req.task_id,
            client_id,
            book_id,
            line_id,
            getattr(req, "tts_engine", "qwen3"),
            elapsed_ms,
            wav_bytes,
            result.duration_ms,
            task_storage_key,
        )
        try:
            requests.post(
                f"{core_internal_url}/tts-complete",
                json={
                    "user_id": client_id,
                    "book_id": book_id,
                    "line_id": line_id,
                    "audio_path": local_audio_uri,
                },
                timeout=20,
            ).raise_for_status()
        except Exception as e:
            logger.warning("core /tts-complete failed; keep stream msg unacked: %s", e)
            return True

        r = _get_redis_client()
        if r:
            try:
                r.xack(_TTS_RENDER_STREAM, _TTS_STAGE4_CONSUMER_GROUP, msg_id)
            except Exception:
                pass
        return True

    batch_size = int(os.getenv("STAGE4_BATCH_SIZE", "1"))
    if batch_size > 1:
        return _process_batch_tasks(batch_size)
    global _empty_poll_count
    try:
        lease = requests.post(f"{core_internal_url}/tts-next", timeout=20)
        if lease.status_code == 404:
            _empty_poll_count += 1
            if _empty_poll_count % 30 == 1:
                logger.info("tts-next empty (stage4 polling %s, queue empty)", core_internal_url)
            return False
        _empty_poll_count = 0
        lease.raise_for_status()
        task = lease.json()
    except Exception as e:
        logger.warning("tts-next request failed: %s", e)
        return False
    req = TTSRequest(
        task_id=task["task_id"],
        user_id=task["user_id"],
        book_id=task["book_id"],
        line_id=task["line_id"],
        text=task["text"],
        speaker=task["voice"],
        emotion=task["emotion"],
        audio_config=task.get("audio_config"),
        speaker_wav_path=task.get("speaker_wav_path"),
        tts_engine=task.get("tts_engine", "qwen3"),
    )
    result = tts(req)
    # При 503 (модель ещё грузится) повторяем запрос несколько раз с паузой
    retry_on_503 = int(os.getenv("STAGE4_TTS_503_RETRIES", "5"))
    retry_delay_sec = int(os.getenv("STAGE4_TTS_503_RETRY_DELAY_SEC", "20"))
    for attempt in range(retry_on_503 - 1):
        if result.status == TTSStatus.DONE:
            break
        err = result.error or ""
        if "503" not in err and "Service Unavailable" not in err:
            break
        logger.info(
            "TTS 503 (model loading?), retry in %ss (%s/%s) book_id=%s line_id=%s",
            retry_delay_sec, attempt + 1, retry_on_503 - 1, req.book_id, req.line_id,
        )
        time.sleep(retry_delay_sec)
        result = tts(req)
    if result.status != TTSStatus.DONE:
        logger.error(
            "TTS failed book_id=%s line_id=%s engine=%s: %s",
            req.book_id, req.line_id, getattr(req, "tts_engine", "qwen3"), result.error or "unknown",
        )
        _task_registry_fail(task_id=req.task_id, error_message=result.error or "tts_failed")
        return True  # уже забрали задачу, но не смогли — не повторяем бесконечно
    try:
        local_audio_uri = result.audio_uri or ""
        task_storage_key = _storage_key_for_task(
            user_id=task["user_id"],
            book_id=task["book_id"],
            line_id=task["line_id"],
            task_id=req.task_id,
            local_audio_uri=local_audio_uri,
        )
        _task_registry_complete(
            task_id=req.task_id,
            storage_key=task_storage_key,
            duration_ms=result.duration_ms,
        )
        requests.post(
            f"{core_internal_url}/tts-complete",
            json={
                "user_id": task["user_id"],
                "book_id": task["book_id"],
                "line_id": task["line_id"],
                "audio_path": local_audio_uri,
            },
            timeout=20,
        ).raise_for_status()
    except Exception:
        pass
    return True


def _process_batch_tasks(batch_size: int) -> bool:
    """Забрать batch задач, озвучить, отправить tts-complete-batch."""
    try:
        lease = requests.post(
            f"{core_internal_url}/tts-next-batch",
            params={"count": batch_size},
            timeout=20,
        )
        if lease.status_code == 404:
            return False
        lease.raise_for_status()
        data = lease.json()
        tasks = data.get("tasks") or []
    except Exception:
        return False
    if not tasks:
        return False
    reqs = [
        TTSRequest(
            task_id=t["task_id"],
            user_id=t["user_id"],
            book_id=t["book_id"],
            line_id=t["line_id"],
            text=t["text"],
            speaker=t["voice"],
            emotion=t.get("emotion"),
            audio_config=t.get("audio_config"),
            speaker_wav_path=t.get("speaker_wav_path"),
            tts_engine=t.get("tts_engine", "qwen3"),
        )
        for t in tasks
    ]
    engine = (tasks[0].get("tts_engine") or "qwen3").strip().lower()
    synth = _synth_for_engine(engine)
    logger.info(
        "TTS engine: %s, book_id=%s, batch_size=%s",
        engine, tasks[0].get("book_id"), len(tasks),
    )
    try:
        batch_results = synth.synthesize_batch(reqs)
    except Exception:
        for t in tasks:
            try:
                _task_registry_fail(task_id=t["task_id"], error_message="tts_batch_failed")
            except Exception:
                pass
        return True  # задачи уже забраны
    if len(batch_results) != len(tasks):
        return True
    results = []
    for (t, (audio_bytes, dur_ms)) in zip(tasks, batch_results):
        target = storage.path_for_line(t["user_id"], t["book_id"], t["line_id"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(audio_bytes)
        audio_uri = storage.uri_for_line(t["user_id"], t["book_id"], t["line_id"])
        results.append({"line_id": t["line_id"], "audio_path": audio_uri})
        task_storage_key = _storage_key_for_task(
            user_id=t["user_id"],
            book_id=t["book_id"],
            line_id=t["line_id"],
            task_id=t["task_id"],
            local_audio_uri=audio_uri or "",
        )
        _task_registry_complete(
            task_id=t["task_id"],
            storage_key=task_storage_key,
            duration_ms=dur_ms,
        )
    try:
        requests.post(
            f"{core_internal_url}/tts-complete-batch",
            json={
                "user_id": tasks[0]["user_id"],
                "book_id": tasks[0]["book_id"],
                "results": results,
            },
            timeout=20,
        ).raise_for_status()
    except Exception:
        pass
    return True


def _worker_loop():
    while True:
        try:
            _process_one_task()
        except Exception:
            pass
        time.sleep(1)


# Фоновый поток: опрос очереди core и озвучка
threading.Thread(target=_worker_loop, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("STAGE4_PORT", "8001")))
