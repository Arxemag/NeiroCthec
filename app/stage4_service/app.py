from __future__ import annotations

import os
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException

from stage4_service.schemas import TTSRequest, TTSResponse, TTSStatus
from stage4_service.storage import LocalObjectStorage
import shutil
from stage4_service.synth import MockSynthesizer

app = FastAPI(title="Stage4 TTS Worker")

synth = MockSynthesizer()
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

    req = TTSRequest(
        task_id=task["task_id"],
        user_id=task["user_id"],
        book_id=task["book_id"],
        line_id=task["line_id"],
        text=task["text"],
        speaker=task["voice"],
        emotion=task["emotion"],
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
