# Задачи на реализацию: стабильность и Docker

По плану из `PLAN-STABILITY-AND-DOCKER.md`. Выполнять по порядку; после каждого блока — проверить сборку/запуск.

---

## Блок 1. Docker: healthchecks и порядок запуска

### Задача 1.1 — Healthcheck для Postgres

**Файл:** `docker-compose.yml`  
**Сервис:** `postgres`

Добавить после `volumes:` (перед следующим сервисом):

```yaml
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U neuro -d neurochtec"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s
```

---

### Задача 1.2 — Healthcheck для Redis

**Файл:** `docker-compose.yml`  
**Сервис:** `redis`

Добавить после `ports:`:

```yaml
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 5s
```

---

### Задача 1.3 — Healthcheck для MinIO

**Файл:** `docker-compose.yml`  
**Сервис:** `minio`

Добавить после `volumes:` (перед следующим сервисом). MinIO не всегда имеет curl в образе — использовать встроенную проверку или установить curl в образе. Вариант без curl:

```yaml
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

Если `mc` нет в образе minio/minio, использовать:

```yaml
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

(Образ `minio/minio` содержит curl.)

---

### Задача 1.4 — Эндпоинт /health для Core и healthcheck

**Файл:** `app/api/app.py`

Добавить маршрут (после создания `app`, до `include_router`):

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

**Файл:** `docker-compose.yml`  
**Сервис:** `core`

Образ Core (python:3.12-slim) не содержит curl. Использовать Python:

```yaml
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

Либо добавить в `app/Dockerfile.core`: `RUN apt-get update && apt-get install -y --no-install-recommends curl && ...` и тогда использовать `curl -f http://localhost:8000/health`.

У **stage4** и **web** в `depends_on` заменить зависимость от core на:

```yaml
core: { condition: service_healthy }
```

(Сейчас у stage4 уже `core: service_started` — поменять на `service_healthy`. У web — добавить или изменить на `service_healthy`.)

---

### Задача 1.5 — Healthcheck для tts-xtts (проверить/увеличить start_period)

**Файл:** `docker-compose.yml`  
**Сервис:** `tts-xtts`

Убедиться, что есть healthcheck (уже добавлен ранее). При необходимости увеличить `start_period` до 300 с (модель долго грузится):

```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8021/health"]
      interval: 15s
      timeout: 5s
      retries: 40
      start_period: 300s
```

---

### Задача 1.6 — Restart policy для stage4

**Файл:** `docker-compose.yml`  
**Сервис:** `stage4`

Добавить на уровень сервиса (рядом с `deploy:`):

```yaml
    restart: on-failure
```

---

## Блок 2. Frontend (Nest API): шимы и импорты

### Задача 2.1 — Создать шим class-validator

**Создать файл:** `frontend/apps/api/src/lib/validators.ts`

Содержимое:

```ts
/**
 * Re-export class-validator via require() to avoid type resolution issues in Docker/workspace.
 */
// eslint-disable-next-line @typescript-eslint/no-require-imports
const cv = require('class-validator');

export const IsString = cv.IsString;
export const IsNumber = cv.IsNumber;
export const IsOptional = cv.IsOptional;
export const IsEmail = cv.IsEmail;
export const IsArray = cv.IsArray;
export const IsObject = cv.IsObject;
export const MinLength = cv.MinLength;
export const MaxLength = cv.MaxLength;
export const Min = cv.Min;
export const Max = cv.Max;
export const ArrayNotEmpty = cv.ArrayNotEmpty;
export const ValidateNested = cv.ValidateNested;
```

---

### Задача 2.2 — Заменить импорты class-validator на шим

Во всех перечисленных файлах заменить импорт с `'class-validator'` на `'../../lib/validators'` (путь от `modules/...` до `lib/` — два уровня вверх).

| Файл | Строка (примерно) |
|------|-------------------|
| `frontend/apps/api/src/modules/auth/dto.ts` | `from 'class-validator'` → `from '../../lib/validators'` |
| `frontend/apps/api/src/modules/admin/dto.ts` | то же |
| `frontend/apps/api/src/modules/voices/dto.ts` | то же |
| `frontend/apps/api/src/modules/books/dto.ts` | то же |
| `frontend/apps/api/src/modules/users/user-voices.dto.ts` | то же |
| `frontend/apps/api/src/modules/projects/dto.ts` | `} from 'class-validator';` → `} from '../../lib/validators';` |

---

### Задача 2.3 — Создать шим @nestjs/platform-express

**Создать файл:** `frontend/apps/api/src/lib/nestjs-platform-express.ts`

Содержимое:

```ts
// eslint-disable-next-line @typescript-eslint/no-require-imports
const platformExpress = require('@nestjs/platform-express');
export const FileInterceptor = platformExpress.FileInterceptor;
```

---

### Задача 2.4 — Заменить импорт FileInterceptor в контроллерах

**Файлы:**

- `frontend/apps/api/src/modules/projects/projects.controller.ts`
- `frontend/apps/api/src/modules/books/books.controller.ts`

Заменить:

- Было: `import { FileInterceptor } from '@nestjs/platform-express';`
- Стало: `import { FileInterceptor } from '../../lib/nestjs-platform-express';`

---

### Задача 2.5 — Зафиксировать версию class-validator

**Файл:** `frontend/apps/api/package.json`

В `dependencies` установить точную версию (без `^`):

```json
"class-validator": "0.13.2"
```

(Если уже `~0.13.2` — оставить или заменить на `0.13.2`.)

---

## Блок 3. Документация и скрипт запуска

### Задача 3.1 — Раздел «Запуск в Docker» в README

**Файл:** `README.md` в корне репозитория (если нет — создать минимальный в корне)

Добавить раздел (или создать README с таким разделом):

```markdown
## Запуск в Docker

1. **Первый запуск (установка зависимостей и Prisma):**
   ```bash
   docker compose up -d frontend_deps
   ```
   Дождаться завершения (контейнер frontend_deps перейдёт в статус Exited 0).

2. **Запуск всего стека:**
   ```bash
   docker compose up -d
   ```

3. **После изменения schema.prisma:**
   ```bash
   docker compose run --rm api sh -c "npm run -w apps/api prisma:generate"
   docker compose restart api worker
   ```
```

---

### Задача 3.2 — Скрипт запуска

**Создать файл:** `scripts/docker-up.sh` (в корне репозитория папка `scripts/`)

Содержимое (bash):

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "Checking frontend_deps..."
if ! docker compose ps frontend_deps 2>/dev/null | grep -q "Exited (0)"; then
  echo "Running frontend_deps (first time or after package changes)..."
  docker compose up -d frontend_deps
  echo "Wait for frontend_deps to complete (exited 0), then run: docker compose up -d"
  exit 0
fi

echo "Starting stack..."
docker compose up -d
echo "Done. Check: docker compose ps"
```

Сделать исполняемым: `chmod +x scripts/docker-up.sh`.

Альтернатива для Windows — создать `scripts/docker-up.ps1` с той же логикой (проверка frontend_deps, затем `docker compose up -d`).

---

### Задача 3.3 — Таблица переменных окружения

**Создать файл:** `docs/ENV.md`

Содержимое (краткая таблица):

```markdown
# Переменные окружения

| Переменная | Где | Описание |
|------------|-----|----------|
| DATABASE_URL | api, worker | PostgreSQL URL (postgresql://user:pass@postgres:5432/dbname) |
| APP_API_URL | api | URL Core API (http://core:8000) |
| NEXT_PUBLIC_APP_API_URL | web | `proxy` или URL Core для браузера |
| API_PROXY_TARGET | web | URL Nest API для прокси /api/* (http://api:4000) |
| APP_API_PROXY_TARGET | web | URL Core для прокси /app-api/* (http://core:8000) |
| EXTERNAL_TTS_XTTS_URL | stage4 | URL TTS XTTS (http://tts-xtts:8021) |
| EXTERNAL_TTS_XTTS_TIMEOUT_SEC | stage4 | Таймаут запроса к XTTS (сек), по умолчанию 600 |
| TTS_USE_GPU | tts-xtts | true/false — использование GPU для XTTS |
| APP_STAGE4_URL | core | URL stage4 для превью (http://stage4:8001) |
```

При необходимости дополнить по существующим переменным в `docker-compose.yml` и `.env.example`.

---

### Задача 3.4 — TROUBLESHOOTING.md

**Создать файл:** `docs/TROUBLESHOOTING.md`

Содержимое:

```markdown
# Типичные ошибки и решения

## Connection refused (stage4 → tts-xtts, api → core и т.д.)

- Убедиться, что все контейнеры запущены: `docker compose ps`.
- Сервисы с healthcheck должны быть в статусе healthy перед стартом зависимых.
- Перезапуск: `docker compose up -d --force-recreate <service>`.

## Cannot find module '.prisma/client/default'

- Выполнить в контейнере api: `docker compose run --rm api sh -c "npm run -w apps/api prisma:generate"`.
- Перезапустить api и worker: `docker compose restart api worker`.

## Module 'class-validator' has no exported member 'IsOptional' / 'Min' / …

- Убедиться, что в коде используются импорты из `../../lib/validators`, а не из `class-validator`.
- Пересобрать зависимости: перезапустить frontend_deps (см. README).

## Read timed out (stage4 → tts-xtts)

- Увеличить таймаут: в docker-compose для stage4 задать `EXTERNAL_TTS_XTTS_TIMEOUT_SEC=900`.
- Проверить логи tts-xtts: `docker compose logs -f tts-xtts` — долгая загрузка модели или медленный инференс.

## Логи

- api: `docker compose logs -f api`
- core: `docker compose logs -f core`
- stage4: `docker compose logs -f stage4`
- tts-xtts: `docker compose logs -f tts-xtts`
```

---

## Блок 4. Опционально (по желанию)

### Задача 4.1 — Повторы запросов в stage4 при сбое TTS

**Файл:** `app/stage4_service/synth.py` (или место вызова ExternalHTTPSynthesizer)

При вызове `synthesize` обернуть в цикл: при `ConnectionError` или `ReadTimeout` повторить до 2–3 раз с паузой 30 с, затем пробросить исключение. (Точное место и сигнатуры — по текущей реализации.)

### Задача 4.2 — Страница «Статус» в приложении

В веб-приложении добавить маршрут (например `/app/status` или в админке), который запрашивает api (4000), core (8000) и при необходимости TTS и отображает доступность. Реализация — по стеку (Next/React).

---

## Чек-лист после реализации

- [ ] `docker compose up -d frontend_deps` завершается с 0.
- [ ] `docker compose up -d` поднимает все сервисы; postgres, redis, minio, core, tts-xtts в состоянии healthy (где задан healthcheck).
- [ ] api и worker стартуют без ошибки Prisma и без ошибок типов class-validator / platform-express.
- [ ] В README есть раздел «Запуск в Docker» и при необходимости ссылка на docs/ENV.md и docs/TROUBLESHOOTING.md.
- [ ] Скрипт `scripts/docker-up.sh` (или .ps1) проверен и документирован в README.

После выполнения блоков 1–3 можно считать реализацию плана завершённой; блок 4 — по желанию.
