# НейроЧтец — SaaS-платформа ИИ-озвучки (MVP scaffold)

Монорепозиторий с:
- `apps/web`: Next.js (TypeScript) — лендинг и личный кабинет
- `apps/api`: NestJS (TypeScript) — REST API, auth, проекты, голоса, аудио

## Запуск целиком через Docker Compose

Теперь весь стек поднимается контейнерами отдельно:
- `web` (Next.js, порт `3000`)
- `api` (NestJS, порт `4000`)
- `worker` (BullMQ worker)
- `postgres` (порт `5432`)
- `redis` (порт `6379`)
- `minio` (S3 API `9000`, console `9001`)

### Быстрый старт

### Вариант запуска из корня репозитория

```bash
# из /workspace/NeiroCthec
docker compose up --build -d
```

Из папки `frontend` (эквивалентный запуск):

```bash
docker compose up --build -d
```

Проверка:

```bash
docker compose ps
```

Открыть:
- `http://localhost:3000` — web
- `http://localhost:4000/api/health` — API healthcheck
- `http://localhost:9001` — MinIO console (`minio` / `minio12345`)

### Остановка

```bash
docker compose down
```

Для полного сброса данных БД/MinIO:

```bash
docker compose down -v
```

## Что делает compose при старте

- Ждёт готовность `postgres` и `redis` через healthcheck, затем стартует `minio`.
- Запускает одноразовый контейнер `api-migrate`, который применяет Prisma-миграции.
- После этого стартуют `api` и `worker`.
- `web` стартует отдельным контейнером и работает с API через `NEXT_PUBLIC_API_BASE_URL`.
- `web` использует проксирование `/api/*` внутри Next на `api:4000`, поэтому кнопки/действия UI ходят в backend через единый origin `http://localhost:3000/api/*`.

## Переменные окружения

Все необходимые значения для контейнеров уже прописаны в `docker-compose.yml`.
Если нужно изменить секреты/лимиты — отредактируйте переменные в сервисах `api`, `worker`, `api-migrate`.

> Важно: корневой `docker-compose.yml` теперь также поднимает Python backend (`backend` на 8000 и `stage4-tts` на 8010), а этот README описывает именно frontend-stack.
