FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN set -eux; \
    for i in {1..5}; do \
        apt-get update -o Acquire::Retries=3 && break; \
        echo "apt-get update failed (attempt $i), retrying..."; \
        sleep 5; \
    done; \
    apt-get install -y --no-install-recommends \
        python3.10 \
        python3-pip \
        ffmpeg \
        libsndfile1; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt \
    && python3 -m pip install --no-cache-dir fastapi~=0.128.0 uvicorn[standard]~=0.40.0

COPY . /app

CMD ["python3", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
