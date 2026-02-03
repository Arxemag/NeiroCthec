# Dockerfile.gpu
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Устанавливаем Python и системные зависимости
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    ffmpeg \
    libsndfile1 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Создаём виртуальное окружение
RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Устанавливаем PyTorch с CUDA поддержкой
RUN pip install --no-cache-dir \
    torch==2.2.2 \
    torchaudio==2.2.2 \
    --index-url https://download.pytorch.org/whl/cu121

# Устанавливаем остальные зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Устанавливаем TTS
RUN pip install --no-cache-dir TTS==0.22.0

# Копируем код
COPY . /app
WORKDIR /app

# Проверяем CUDA
RUN python -c "import torch; print('='*60); print('PyTorch версия:', torch.__version__); print('CUDA доступна:', torch.cuda.is_available()); print('CUDA версия:', torch.version.cuda); print('='*60)"

CMD ["python", "test_gpu_tts.py"]