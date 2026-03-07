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

### 2. Вариант «всё из корня» (рекомендуется)

В корне проекта лежит единый `docker-compose.yml`, который поднимает все сервисы одной командой:

```bat
cd NeiroCthec
docker compose up -d
```

Будут запущены: **postgres**, **redis**, **minio**, **core**, **stage4**, **api**, **worker**, **web**. Контейнер **tts** (NVIDIA) по умолчанию не стартует — он в профиле `nvidia-tts`. На машине с AMD после этого нужно только поднять локальный TTS (см. раздел 4, вариант A). На машине с NVIDIA можно дополнительно включить TTS:

```bat
docker compose --profile nvidia-tts up -d
```

и при необходимости направить Stage4 на контейнер TTS через переменную `EXTERNAL_TTS_URL=http://tts:8020` (например, в `docker-compose.override.yml` для сервиса `stage4`).

Остановка всего стека:

```bat
docker compose down
```

---

### 3. Инфраструктура + Frontend по отдельности (из папки frontend)

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

### 4. Core API и Stage4 по отдельности (из папки app)

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

### 5. TTS Qwen3

Используется **только модель Base 4-bit** (`divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit`): синтез только по образцу голоса (voice clone). Для каждого запроса нужен WAV в `storage/voices` или в запросе (`voice_sample` / голос из настроек). Для 4-bit в окружении должны быть установлены `bitsandbytes` и `accelerate`.

#### Вариант A — локальный TTS на AMD (рекомендуется для вас)

Запускается **вне Docker** на хосте:

```bat
cd app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install "bitsandbytes>=0.42.0" accelerate
python -m tts_engine_service.app    # слушает порт 8020
```

При проблемах с 4-bit на ROCm можно переопределить модель: `set TTS_QWEN3_BASE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base` (полная Base без квантизации).

Stage4 в контейнере по умолчанию обращается к TTS по адресу:

```text
EXTERNAL_TTS_URL=http://host.docker.internal:8020
```

то есть к локальному TTS на хосте.

#### Вариант B — TTS в Docker (для NVIDIA‑машины коллеги)

Из корня проекта:

```bat
docker compose -f docker-compose.yml -f docker-compose.nvidia-tts.yml --profile nvidia-tts up -d
```

Файл `docker-compose.nvidia-tts.yml` переопределяет `EXTERNAL_TTS_URL=http://tts:8020`, чтобы Stage4 обращался к контейнеру TTS, а не к хосту. Образ TTS уже включает `bitsandbytes` и `accelerate` для 4-bit модели.

#### Несколько воркеров Stage4 (вариант A)

В `docker-compose.yml` у сервиса `stage4` задано `deploy.replicas: 2`. Все реплики обращаются к одному Core (`tts-next` / `tts-next-batch`); каждая задача выдаётся один раз. Чтобы поднять больше воркеров (2–4 в зависимости от нагрузки):

```bat
docker compose up -d --scale stage4=4
```

---

### 6. Остановка сервисов

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

### 7. Дебаг: проверка поднятия контейнеров

Скрипт по шагам проверяет конфигурацию, создаёт `.env` из примеров при отсутствии, поднимает весь стек и выводит статус и логи:

```bat
cd NeiroCthec
powershell -ExecutionPolicy Bypass -File scripts/docker-debug.ps1
```

Если путь к проекту содержит квадратные скобки (например `[01]`), запускайте из корня проекта так, чтобы текущая папка была `NeiroCthec`, иначе используйте:

```bat
cd /d "C:\Users\...\Documents\[01] My Projects\NeiroCthec"
docker compose config
docker compose up -d
docker compose ps -a
docker compose logs -f api
```

---

### 8. Частые проблемы

- **Финальный WAV не собирается (фрагменты line_*.wav есть)**:
  - финальный WAV собирает **Core API** (не TTS). TTS только синтезирует фрагменты, Stage4 сохраняет их в `storage/books/.../lines/`, Core склеивает в `final.wav`.
  - проверьте, что Core и Stage4 используют один и тот же storage: в `docker-compose` задан `APP_STORAGE_ROOT=/app/storage` для обоих.
  - если Core перезапускался после озвучки — состояние пайплайна (`_book_states`) в памяти теряется, сборка не сработает. Перезапустите озвучку книги.
  - фронтенд должен вызывать Core (порт 8000) для скачивания: `NEXT_PUBLIC_APP_API_URL=http://localhost:8000`. Скачивание (`GET /books/:id/download`) запускает сборку.
  - при TTS в Docker: используйте `docker-compose.nvidia-tts.yml`, чтобы Stage4 обращался к `http://tts:8020`.

- **Core API или Stage4 не видят TTS**:
  - убедитесь, что TTS слушает `http://localhost:8020` (локально) или контейнер `tts` запущен и `EXTERNAL_TTS_URL` указывает на `http://tts:8020`;
  - на Windows для доступа из контейнера к хосту используйте `host.docker.internal`.

- **Ошибки api/worker (EEXIST, symlink, napi-postinstall)**:
  - зависимости фронта один раз ставит сервис `frontend_deps`; после него стартуют `api`, `worker`, `web`. Если в volume остался старый `node_modules`, удалите его и поднимите стек заново:
    ```bat
    docker compose down
    docker volume rm neirocthec_frontend_node_modules 2>nul
    docker compose up -d
    ```
  - если при установке падает скрипт `napi-postinstall`, можно пересобрать с пропуском скриптов: в корневом `docker-compose.yml` у сервиса `frontend_deps` в `command` заменить `npm install` на `npm install --ignore-scripts`, затем снова `docker compose up -d` (при необходимости предварительно удалить volume `frontend_node_modules`).

- **Web: EACCES permission denied в `apps/web/.next`**:
  - в `docker-compose` для сервиса `web` добавлен том `frontend_web_next` для каталога `apps/web/.next`, чтобы артефакты сборки Next.js не писались в примонтированную папку и не вызывали конфликта прав. Если ошибка появилась до этого изменения — пересоздайте контейнер и при необходимости удалите старый кэш:
    ```bat
    docker compose down
    docker compose up -d web
    ```
  - при необходимости можно вручную удалить папку `frontend/apps/web/.next` на хосте (остановив контейнер), после чего поднять `web` снова.

- **NestJS или Next.js не стартуют**:
  - смотрите логи:
    ```bat
    docker compose logs -f api
    docker compose logs -f web
    ```

---

### Корзина книг и очистка через 7 дней

Удалённые книги (раздел «Мои книги» → «Корзина») хранятся в БД 7 дней. Пользователь может восстановить книгу до истечения срока — тогда запись и файлы остаются. Чтобы безвозвратно удалять книги из корзины через 7 дней, настройте вызов по расписанию:

1. В `frontend/apps/api/.env` задайте секрет: `CRON_SECRET=ваш_секретный_токен`.
2. Раз в день вызывайте (с хоста или из cron в контейнере):
   ```bash
   curl -X POST -H "X-Cron-Secret: ваш_секретный_токен" http://localhost:4000/api/books/purge-trash
   ```
   В Docker, если API доступен по имени сервиса: `http://api:4000/api/books/purge-trash`.

