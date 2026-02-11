# NeiroCthec: запуск всего стека в Docker

Если хочешь поднять всё одной командой **из корня репозитория**, используй:

```bash
docker compose up --build -d
```

Остановить:

```bash
docker compose down
```

Полный сброс данных:

```bash
docker compose down -v
```

## Какие контейнеры поднимаются

- `web` — Next.js (`http://localhost:3000`)
- `api` — NestJS (`http://localhost:4000`)
- `worker` — фоновые задачи генерации
- `postgres` — БД (`5432`)
- `redis` — очередь/кэш (`6379`)
- `minio` — S3-совместимое хранилище (`9000`, console `9001`)

Проверка статуса:

```bash
docker compose ps
```

Логи:

```bash
docker compose logs -f
```

> Детальные пояснения по frontend-части: `frontend/README.md`.
