# НейроЧтец

Стек: Core API (Python/FastAPI), Stage4 + TTS (XTTS2/Qwen3), Nest API + Next.js, Postgres, Redis, MinIO.

## Запуск в Docker

1. **Первый запуск (установка зависимостей и Prisma):**
   ```bash
   docker compose up -d frontend_deps
   ```
   Дождаться завершения (контейнер `frontend_deps` перейдёт в статус Exited 0).

2. **Запуск всего стека:**
   ```bash
   docker compose up -d
   ```
   Либо использовать скрипт: `./scripts/docker-up.sh` (см. ниже).

3. **После изменения schema.prisma:**
   ```bash
   docker compose run --rm api sh -c "npm run -w apps/api prisma:generate"
   docker compose restart api worker
   ```

Подробнее: [docs/ENV.md](docs/ENV.md) (переменные окружения), [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) (типичные ошибки).
