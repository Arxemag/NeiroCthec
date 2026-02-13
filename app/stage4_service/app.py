from __future__ import annotations

import logging
import os
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException

from stage4_service.logging_utils import get_stage4_logger, setup_logging
from stage4_service.schemas import TTSRequest, TTSResponse, TTSStatus
from stage4_service.storage import LocalObjectStorage
import shutil
from stage4_service.synth import ExternalHTTPSynthesizer, MockSynthesizer

app = FastAPI(title="Stage4 TTS Worker")
setup_logging()
logger = logging.getLogger("stage4")


def _build_synth():
    mode = os.getenv("STAGE4_SYNTH_MODE", "mock").strip().lower()
    if mode == "external":
        base_url = os.getenv("EXTERNAL_TTS_URL", "http://tts-engine:8020")
        timeout = int(os.getenv("EXTERNAL_TTS_TIMEOUT_SEC", "60"))
        logger.info("stage4 synth mode=external base_url=%s timeout=%s", base_url, timeout)
        return ExternalHTTPSynthesizer(base_url=base_url, timeout_sec=timeout)
    logger.info("stage4 synth mode=mock")
    return MockSynthesizer()


synth = _build_synth()
storage = LocalObjectStorage()
core_internal_url = os.getenv("CORE_INTERNAL_URL", "http://api:8000/internal")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tts", response_model=TTSResponse)
def tts(request: TTSRequest):
    task_logger = get_stage4_logger(request.task_id, request.user_id, request.book_id, request.line_id)
    try:
        relative = Path(request.user_id) / request.book_id / f"line_{request.line_id}.wav"
        tmp_path = Path("/tmp") / relative
        target = storage.path_for_line(request.user_id, request.book_id, request.line_id)
        task_logger.info(
            (
                "tts start: speaker=%s language=%s audio_config_keys=%s "
                "tmp_path=%s target_path=%s"
            )
            % (
                request.speaker,
                request.language,
                sorted((request.audio_config or {}).keys()) if isinstance(request.audio_config, dict) else [],
                str(tmp_path),
                str(target),
            )
        )

        duration_ms = synth.synthesize(request=request, output_path=tmp_path)
        shutil.copyfile(tmp_path, target)
        audio_uri = storage.uri_for_line(request.user_id, request.book_id, request.line_id)
        task_logger.info("tts done: duration_ms=%s audio_uri=%s", duration_ms, audio_uri)
        return TTSResponse(task_id=request.task_id, status=TTSStatus.DONE, audio_uri=audio_uri, duration_ms=duration_ms)
    except Exception as exc:
        task_logger.exception(f"tts failed: {exc}")
        return TTSResponse(task_id=request.task_id, status=TTSStatus.ERROR, error=str(exc))


@app.post("/process-next")
def process_next_task():
    logger.info("process-next: requesting lease from %s/tts-next", core_internal_url)
    lease = requests.post(f"{core_internal_url}/tts-next", timeout=20)
    if lease.status_code == 404:
        logger.info("process-next: queue is empty")
        return {"status": "empty"}
    lease.raise_for_status()
    task = lease.json()

    audio_config = task.get("audio_config")
    language_raw = task.get("language")
    language = language_raw.strip() if isinstance(language_raw, str) and language_raw.strip() else None
    if language is None and isinstance(audio_config, dict):
        engine = audio_config.get("engine")
        if isinstance(engine, dict):
            lang = engine.get("language")
            if isinstance(lang, str) and lang.strip():
                language = lang.strip()

    req = TTSRequest(
        task_id=task["task_id"],
        user_id=task["user_id"],
        book_id=task["book_id"],
        line_id=task["line_id"],
        text=task["text"],
        speaker=task["voice"],
        emotion=task["emotion"],
        audio_config=audio_config,
        language=language,
    )

    task_logger = get_stage4_logger(req.task_id, req.user_id, req.book_id, req.line_id)
    task_logger.info(
        "lease received: speaker=%s language=%s audio_config=%s",
        req.speaker,
        req.language,
        req.audio_config,
    )

    result = tts(req)
    if result.status != TTSStatus.DONE:
        raise HTTPException(status_code=500, detail=result.error or "TTS failed")

    task_logger.info("notify core /tts-complete line_id=%s audio_uri=%s", task["line_id"], result.audio_uri)
    requests.post(
        f"{core_internal_url}/tts-complete",
        json={"line_id": task["line_id"], "audio_path": result.audio_uri},
        timeout=20,
    ).raise_for_status()

    task_logger.info("process-next completed")
    return {"status": "processed", "line_id": task["line_id"], "audio_path": result.audio_uri}
