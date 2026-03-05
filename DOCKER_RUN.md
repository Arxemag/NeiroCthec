### Запуск НейроЧтец в Docker (dev)

Ниже — минимальный набор команд, чтобы поднять **весь стек через Docker**, оставив **TTS Qwen3** локальным (AMD) или в отдельном контейнере (NVIDIA).

---

### 1. Предварительные требования

- Docker Desktop (Windows / macOS) или Docker на Linux.
- Для NVIDIA‑GPU: установленный драйвер и NVIDIA Container Toolkit.
- Репозиторий склонирован и актуален:
  ```bash
  git pull
  ```
- Для фронтенда: скопированы `.env` из примеров:
  ```bat
  cd frontend
  copy .env.example .env           # опционально
  copy apps\api\.env.example apps\api\.env
  copy apps\web\.env.example apps\web\.env
  ```

---

### 2. Инфраструктура + Frontend (API, Worker, Web)

Из папки `frontend/`:

```bat
cd frontend
docker compose up -d
```

Это поднимет:

- `postgres` (порт 5432)
- `redis` (порт 6379)
- `minio` (9000/9001)
- `api` (NestJS, порт 4000)
- `worker` (BullMQ)
- `web` (Next.js, порт 3000)

Код фронтенда и API монтируется как том `./frontend:/usr/src/app`, так что изменения в `.ts/.tsx` видны без пересборки (hot‑reload).

---

### 3. Core API и Stage4 в Docker

Из папки `app/`:

```bat
cd app
docker compose up -d core stage4
```

Поднимаются:

- `core` — Core API (FastAPI) на `http://localhost:8000`
- `stage4` — воркер пайплайна TTS (stage4_service), который дергает Core API по `http://core:8000/internal`

Обе службы монтируют:

- весь каталог `app` → `/app` (hot‑reload кода пайплайна);
- `./storage` → `/app/storage` (общий каталог с WAV‑файлами книг).

---

### 4. TTS Qwen3

#### Вариант A — локальный TTS на AMD (рекомендуется для вас)

Запускается **вне Docker** на хосте:

```bat
cd app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m tts_engine_service.app    # слушает порт 8020
```

Stage4 в контейнере по умолчанию обращается к TTS по адресу:

```text
EXTERNAL_TTS_URL=http://host.docker.internal:8020
```

то есть к локальному TTS на хосте.

#### Вариант B — TTS в Docker (для NVIDIA‑машины коллеги)

Из папки `app/`:

```bat
cd app
docker compose up -d tts
```

По умолчанию `stage4` настроен на `http://host.docker.internal:8020`.  
Для использования контейнера TTS можно переопределить `EXTERNAL_TTS_URL`, например, через `docker-compose.override.yml`:

```yaml
services:
  stage4:
    environment:
      EXTERNAL_TTS_URL: http://tts:8020
```

и затем:

```bat
docker compose up -d stage4 tts
```

---

### 5. Остановка сервисов

- Фронтенд и инфраструктура:
  ```bat
  cd frontend
  docker compose down
  ```

- Core / Stage4 / TTS:
  ```bat
  cd app
  docker compose down
  ```

---

### 6. Частые проблемы

- **Core API или Stage4 не видят TTS**:
  - убедитесь, что TTS слушает `http://localhost:8020` (локально) или контейнер `tts` запущен и `EXTERNAL_TTS_URL` указывает на `http://tts:8020`;
  - на Windows для доступа из контейнера к хосту используйте `host.docker.internal`.

- **NestJS или Next.js не стартуют**:
  - смотрите логи:
    ```bat
    cd frontend
    docker compose logs -f api
    docker compose logs -f web
    ```

