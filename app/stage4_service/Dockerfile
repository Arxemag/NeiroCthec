FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    for i in {1..5}; do \
        apt-get update -o Acquire::Retries=3 && break; \
        echo "apt-get update failed (attempt $i), retrying..."; \
        sleep 5; \
    done; \
    apt-get install -y --no-install-recommends \
        python3.10 \
        python3-pip \
        python3.10-venv \
        ffmpeg \
        libsndfile1; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY stage4_service/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY stage4_service /srv/stage4_service

ENV PYTHONPATH=/srv
ENV STAGE4_MAX_GPU_JOBS=1
ENV STAGE4_WORKERS=1

CMD ["uvicorn", "stage4_service.app:app", "--host", "0.0.0.0", "--port", "8010"]
