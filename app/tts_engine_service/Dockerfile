FROM python:3.11-slim

WORKDIR /srv
COPY tts_engine_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY tts_engine_service ./tts_engine_service

CMD ["python3", "-m", "uvicorn", "tts_engine_service.app:app", "--host", "0.0.0.0", "--port", "8020"]
