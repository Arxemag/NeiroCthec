from __future__ import annotations

import os
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException

from stage4_service.schemas import TTSRequest, TTSResponse, TTSStatus
from stage4_service.storage import LocalObjectStorage
import shutil
from stage4_service.synth import ExternalHTTPSynthesizer, MockSynthesizer

app = FastAPI(title="Stage4 TTS Worker")



def _build_synth():
    mode = os.getenv("STAGE4_SYNTH_MODE", "mock").strip().lower()
    if mode == "external":
        base_url = os.getenv("EXTERNAL_TTS_URL", "http://tts-engine:8020")
        timeout = int(os.getenv("EXTERNAL_TTS_TIMEOUT_SEC", "60"))
        return ExternalHTTPSynthesizer(base_url=base_url, timeout_sec=timeout)
    return MockSynthesizer()


synth = _build_synth()
storage = LocalObjectStorage()
core_internal_url = os.getenv("CORE_INTERNAL_URL", "http://api:8000/internal")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tts", response_model=TTSResponse)
def tts(request: TTSRequest):
    try:
        relative = Path(request.user_id) / request.book_id / f"line_{request.line_id}.wav"
        tmp_path = Path("/tmp") / relative
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

    audio_config = task.get("audio_config")
    language = None
    if isinstance(audio_config, dict):
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

    result = tts(req)
    if result.status != TTSStatus.DONE:
        raise HTTPException(status_code=500, detail=result.error or "TTS failed")

    requests.post(
        f"{core_internal_url}/tts-complete",
        json={"line_id": task["line_id"], "audio_path": result.audio_uri},
        timeout=20,
    ).raise_for_status()

    return {"status": "processed", "line_id": task["line_id"], "audio_path": result.audio_uri}
