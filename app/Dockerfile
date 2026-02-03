FROM python:3.11-slim

# Устанавливаем системные зависимости включая ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV COQUI_TOS_AGREED=1
ENV TTS_HOME=/app/storage/models

# Для Natasha (опционально) предзагружаем модели
RUN pip install --no-cache-dir razdel natasha && \
    python -c "from natasha import NewsEmbedding; NewsEmbedding()" 2>/dev/null || true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/storage/models

CMD ["python", "main.py"]
