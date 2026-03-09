from __future__ import annotations

import logging
import os

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
from stage4_service.storage import LocalObjectStorage
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
    url_qwen3 = os.getenv("EXTERNAL_TTS_QWEN3_URL", os.getenv("EXTERNAL_TTS_URL", "http://host.docker.internal:8020")).strip().rstrip("/")
    url_xtts = os.getenv("EXTERNAL_TTS_XTTS_URL", "http://tts-xtts:8021").strip().rstrip("/")
    return {
        "qwen3": _build_synth(mode, url_qwen3, timeout),
        "xtts2": _build_synth(mode, url_xtts, timeout),
    }


_synthesizers = _get_synthesizers()


def _synth_for_engine(tts_engine: str | None):
    e = (tts_engine or "qwen3").strip().lower()
    return _synthesizers.get(e) or _synthesizers["qwen3"]
storage = LocalObjectStorage()
# Без пробелов и без завершающего слэша, иначе получится /internal%20/tts-next и 404
core_internal_url = (os.getenv("CORE_INTERNAL_URL", "http://api:8000/internal") or "").strip().rstrip("/")
# Счётчик опросов с пустой очередью — раз в ~30 сек пишем в лог, что воркер жив и опрашивает core
_empty_poll_count = 0


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tts", response_model=TTSResponse)
def tts(request: TTSRequest):
    engine = (getattr(request, "tts_engine", None) or "qwen3").strip().lower()
    synth = _synth_for_engine(engine)
    url = getattr(synth, "base_url", None) or "(mock)"
    logger.info("tts task book_id=%s line_id=%s engine=%s url=%s", request.book_id, request.line_id, engine, url)
    try:
        relative = Path(request.user_id) / request.book_id / f"line_{request.line_id}.wav"
        tmp_path = Path(tempfile.gettempdir()) / relative
        duration_ms = synth.synthesize(request=request, output_path=tmp_path)
        target = storage.path_for_line(request.user_id, request.book_id, request.line_id)
        shutil.copyfile(tmp_path, target)
        audio_uri = storage.uri_for_line(request.user_id, request.book_id, request.line_id)
        return TTSResponse(task_id=request.task_id, status=TTSStatus.DONE, audio_uri=audio_uri, duration_ms=duration_ms)
    except Exception as exc:
        return TTSResponse(task_id=request.task_id, status=TTSStatus.ERROR, error=str(exc))


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
        return True  # уже забрали задачу, но не смогли — не повторяем бесконечно
    try:
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
    try:
        batch_results = synth.synthesize_batch(reqs)
    except Exception:
        return True  # задачи уже забраны
    if len(batch_results) != len(tasks):
        return True
    results = []
    for (t, (audio_bytes, _)) in zip(tasks, batch_results):
        target = storage.path_for_line(t["user_id"], t["book_id"], t["line_id"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(audio_bytes)
        audio_uri = storage.uri_for_line(t["user_id"], t["book_id"], t["line_id"])
        results.append({"line_id": t["line_id"], "audio_path": audio_uri})
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
