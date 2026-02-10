FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.10 python3-pip python3.10-venv ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY stage4_service/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY stage4_service /srv/stage4_service

ENV PYTHONPATH=/srv
ENV STAGE4_MAX_GPU_JOBS=1
ENV STAGE4_WORKERS=1

CMD ["uvicorn", "stage4_service.app:app", "--host", "0.0.0.0", "--port", "8010"]
