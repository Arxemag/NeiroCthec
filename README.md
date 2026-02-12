# NeiroCthec: запуск стека в Docker

Причина вашей ошибки — не код Dockerfile, а сеть до Docker Hub (`failed to fetch anonymous token ... connection failed`).
Из‑за этого сборка одного образа падает и Compose отменяет остальные (`npm ci ... CANCELED`).

Чтобы можно было стабильно поднимать фронт даже при проблемах с Python-образами, я разделил запуск по профилям.

## 1) Быстрый запуск фронтового стека (по умолчанию)

```bash
docker compose up --build -d
```

Поднимает:
- `web` (`http://localhost:3000`)
- В Dockerfile для web/api используется `npm ci --include=dev`, чтобы на этапе сборки были доступны TypeScript/Next/Nest dev-зависимости.
- `api` Nest (`http://localhost:4000`)
- `worker`
- `postgres` (`5432`), `redis` (`6379`), `minio` (`9000/9001`)

## 2) Полный запуск, включая Python backend

```bash
docker compose --profile python-backend up --build -d
```

Дополнительно поднимает:
- `backend` FastAPI (`http://localhost:8000`)
- `stage4-tts` (`http://localhost:8010`)
- `py-postgres` (`localhost:5433`)

## Остановка

```bash
docker compose down
```

Полный сброс томов:

```bash
docker compose down -v
```

## Проверка

```bash
docker compose ps
docker compose logs -f web api backend stage4-tts
```

## Если снова ловите ошибку token response

Это временная проблема сети/доступа к registry. Обычно помогает:

```bash
docker pull python:3.10-slim
docker pull node:20-alpine
docker compose --profile python-backend up --build -d
```

> Детальные пояснения по frontend-части: `frontend/README.md`.
