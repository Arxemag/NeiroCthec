### Запуск НейроЧтец в Docker (dev)

Ниже — минимальный набор команд, чтобы поднять **весь стек через Docker**. **XTTS2** работает только в контейнере `tts-xtts` (порт 8021). **Qwen3** по умолчанию — локально на хосте (8020); при необходимости можно поднять и его в Docker (профиль `nvidia-tts`).

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

Будут запущены: **postgres**, **redis**, **minio**, **core**, **stage4**, **api**, **worker**, **web**, **tts-xtts** (порт 8021). **tts-qwen3** (порт 8020) по умолчанию не стартует — он в профиле `nvidia-tts`; Qwen3 ожидается локально на хосте (`EXTERNAL_TTS_QWEN3_URL=http://host.docker.internal:8020`). XTTS2 всегда в контейнере: Stage4 обращается к нему по `EXTERNAL_TTS_XTTS_URL=http://tts-xtts:8021`.

Чтобы поднять и Qwen3 в Docker (оба TTS в контейнерах):

```bat
docker compose -f docker-compose.yml -f docker-compose.nvidia-tts.yml --profile nvidia-tts up -d
```

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

### 5. TTS: Qwen3 (8020) и XTTS2 (8021)

Два движка: **Qwen3** (порт 8020) и **XTTS2 / Coqui** (порт 8021). На фронте в настройках проекта можно выбрать движок; Stage4 по полю `tts_engine` в задаче вызывает соответствующий URL.

- **EXTERNAL_TTS_QWEN3_URL** — адрес Qwen3 (по умолчанию `http://host.docker.internal:8020` — локальный процесс на хосте).
- **EXTERNAL_TTS_XTTS_URL** — адрес XTTS2 (по умолчанию `http://tts-xtts:8021` — контейнер в том же compose).

#### TTS Qwen3 (локально или в Docker)

Модель Base 4-bit (`divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit`): синтез по образцу голоса (voice clone). По умолчанию Stage4 обращается к хосту (`host.docker.internal:8020`) — запустите локально: `cd app`, `.venv\Scripts\activate`, `python -m tts_engine_service.app`. Чтобы поднять Qwen3 в Docker: `docker compose -f docker-compose.yml -f docker-compose.nvidia-tts.yml --profile nvidia-tts up -d` (см. выше).

#### TTS XTTS2 (только Docker)

XTTS2 работает **только в контейнере** `tts-xtts` (порт 8021). Контейнер входит в стандартный пул и собирается вместе с остальными при `docker compose up -d`. Stage4 обращается к нему по `http://tts-xtts:8021`. Подробнее: [docs/TTS_XTTS2.md](docs/TTS_XTTS2.md).

#### Несколько воркеров Stage4

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
  - при Qwen3 в Docker: используйте `docker-compose.nvidia-tts.yml` с профилем `nvidia-tts`, чтобы Stage4 обращался к `http://tts-qwen3:8020`. XTTS2 всегда идёт на `http://tts-xtts:8021`.

- **Озвучка с фронта не идёт / нет запросов в TTS**:
  - Очередь задач (tts-next) хранится **в памяти Core**. После перезапуска контейнера `core` она пуста. Нажмите «Сгенерировать озвучку» ещё раз — пайплайн заново сформирует задачи и добавит книгу в очередь.
  - Если в Core видите `enqueued=True` и `remaining_tasks=N`, но в логах Core нет вызовов `tts-next`, а в stage4 логов нет — **контейнер stage4 не опрашивает Core**. Проверьте: `docker compose ps` (stage4 в статусе Up?), `docker compose logs stage4 --tail 30`. Должны быть строки либо `tts task ...` (есть задачи), либо раз в ~30 сек `tts-next empty (stage4 polling ...)` (очередь пуста, но воркер жив). Если логов нет — перезапустите stage4; убедитесь, что в окружении stage4 задано `CORE_INTERNAL_URL=http://core:8000/internal` (в корневом compose так и есть).
  - Если все строки книги уже озвучены (есть `lines/line_*.wav` и не менялись голоса/движок), в очередь ничего не добавляется. На фронте появится подсказка; чтобы переозвучить — смените движок TTS (например на XTTS2) или голоса и снова нажмите «Сгенерировать озвучку».
  - В логах Core смотрите: `process-book-stage4 request book_id=...` (запрос дошёл), `remaining_tasks=N enqueued=True` (задачи в очереди), `tts-next: issued task ...` (stage4 забрал задачу), `tts-next: queue empty` (воркер опрашивает, но очередь пуста). В логах stage4: `tts task ... engine=xtts2 url=...` — запросы уходят в TTS.

- **Core API или Stage4 не видят TTS**:
  - Qwen3 по умолчанию на хосте (8020), XTTS2 — в контейнере `tts-xtts` (8021). Убедитесь, что контейнер `tts-xtts` запущен и переменные `EXTERNAL_TTS_QWEN3_URL`, `EXTERNAL_TTS_XTTS_URL` заданы для stage4;
  - на Windows для доступа из контейнера к локальному Qwen3 используйте `host.docker.internal`.

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

