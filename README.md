# NeiroCthec: запуск всего стека в Docker

Теперь в корневом `docker-compose.yml` поднимаются **оба бэкенда**:
- фронтовый backend (`frontend/apps/api`, NestJS, порт `4000`)
- основной backend (`app/api`, FastAPI, порт `8000`) + `stage4-tts` (порт `8010`)

## Запуск из корня репозитория

```bash
docker compose up --build -d
```

## Остановка

```bash
docker compose down
```

Полный сброс томов:

```bash
docker compose down -v
```

## Что поднимается

### Frontend stack
- `web` — Next.js (`http://localhost:3000`)
- `api` — NestJS (`http://localhost:4000`)
- `worker` — фоновые задачи
- `postgres` — БД для Nest (`localhost:5432`)
- `redis` — очередь/кэш (`localhost:6379`)
- `minio` — хранилище (`localhost:9000`, console `localhost:9001`)

### Core backend stack
- `backend` — FastAPI (`http://localhost:8000`)
- `stage4-tts` — TTS-сервис (`http://localhost:8010`)
- `py-postgres` — БД для FastAPI (`localhost:5433` -> container `5432`)

## Проверка

```bash
docker compose ps
docker compose logs -f backend api web
```

> Отдельные пояснения по frontend-части: `frontend/README.md`.
