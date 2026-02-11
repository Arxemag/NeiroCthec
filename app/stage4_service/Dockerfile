FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY stage4_service/requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements.txt

COPY stage4_service /srv/stage4_service

ENV PYTHONPATH=/srv
ENV STAGE4_MAX_GPU_JOBS=1
ENV STAGE4_WORKERS=1

CMD ["python3", "-m", "uvicorn", "stage4_service.app:app", "--host", "0.0.0.0", "--port", "8010"]
