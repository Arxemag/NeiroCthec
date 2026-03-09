# Типичные ошибки и решения

## Connection refused (stage4 → tts-xtts, api → core и т.д.)

- Убедиться, что все контейнеры запущены: `docker compose ps`.
- Сервисы с healthcheck должны быть в статусе **healthy** перед стартом зависимых.
- Перезапуск: `docker compose up -d --force-recreate <service>`.

## Cannot find module 'reflect-metadata' (или другой модуль из node_modules)

- В docker-compose для api и worker задана переменная `NODE_PATH=/usr/src/app/node_modules`. Перезапустите: `docker compose restart api worker`.
- Если ошибка остаётся — пересоберите зависимости: `docker compose up -d frontend_deps`, дождитесь выхода, затем `docker compose up -d`.

## Cannot find module '.prisma/client/default'

- Выполнить в контейнере api:  
  `docker compose run --rm api sh -c "npm run -w apps/api prisma:generate"`.
- Перезапустить api и worker: `docker compose restart api worker`.

## Module 'class-validator' has no exported member 'IsOptional' / 'Min' / …

- Убедиться, что в коде используются импорты из `../../lib/validators`, а не из `class-validator`.
- Пересобрать зависимости: перезапустить frontend_deps (см. README).

## Read timed out (stage4 → tts-xtts)

- Увеличить таймаут: в docker-compose для stage4 задать `EXTERNAL_TTS_XTTS_TIMEOUT_SEC=900`.
- Проверить логи tts-xtts: `docker compose logs -f tts-xtts` — долгая загрузка модели или медленный инференс.

## В stage4 ничего не приходит после «Сгенерировать озвучку»

- В логах **core** найдите строку `process-book-stage4 outcome: book_id=... pending=... done=... enqueued=...`. Если **enqueued=False** и **pending=0** — Core считает все строки уже озвученными. Включите чекбокс **«Принудительно переозвучить»** на странице проекта и нажмите «Сгенерировать озвучку» снова (или смените движок TTS/голоса).
- **Выбрать движок XTTS2** на странице проекта, если нужна озвучка через XTTS (по умолчанию Qwen3).
- При использовании **proxy** (NEXT_PUBLIC_APP_API_URL=proxy) запросы к Core теперь идут через явный прокси `/app-api/*`, чтобы тело POST (в т.ч. `tts_engine`) не терялось.
- Проверить логи:
  - **core**: `docker compose logs -f core` — должна быть строка `process-book-stage4 request ... body.tts_engine=xtts2` и затем `enqueued=True tts_engine=xtts2`.
  - **stage4**: `docker compose logs -f stage4` — строки `TTS engine=xtts2` и `External TTS request: POST http://tts-xtts:8021/synthesize`.
  - **tts-xtts**: `docker compose logs -f tts-xtts` — появление запросов POST /synthesize.
- Убедиться, что контейнеры stage4 и tts-xtts запущены и (для tts-xtts) healthy: `docker compose ps`.

## Логи

- api: `docker compose logs -f api`
- core: `docker compose logs -f core`
- stage4: `docker compose logs -f stage4`
- tts-xtts: `docker compose logs -f tts-xtts`
