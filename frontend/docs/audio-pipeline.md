# Audio pipeline (MVP)

## Цель

Асинхронная генерация аудио (text → voice(s) → audio) с:
- хранением результата в S3-совместимом хранилище (MinIO),
- **стримингом только через backend** (без публичных URL),
- подготовкой к масштабированию воркеров.

## Компоненты

- **API**: `apps/api` (NestJS)\n+  - создаёт `Audio(status=queued)`\n+  - ставит задачу в BullMQ\n+- **Queue**: BullMQ (`Redis`) очередь `neurochtec`, job `generate-audio`\n+- **Worker**: `npm run -w apps/api worker` (`apps/api/src/worker.ts`)\n+  - берёт job\n+  - генерирует аудио (в MVP — заглушка: 1 секунда тишины WAV)\n+  - кладёт файл в S3/MinIO\n+  - обновляет `Audio(storageKey,status=ready)` и `Project(status=ready)`\n+- **Storage**: S3/MinIO bucket `S3_BUCKET`\n+
## Контракты\n+
### Запуск генерации\n+
- `POST /api/projects/:id/generate-audio`\n+  - checks: ownership, лимиты (free), базовые ограничения текста\n+  - side effects:\n+    - `Audio` создаётся с `queued`\n+    - `Project.status` → `queued`\n+    - enqueue job `{ audioId }`\n+\n+### Стриминг\n+\n+- `GET /api/audios/:id/stream`\n+  - checks: ownership, `Audio.status=ready`, `storageKey` присутствует\n+  - backend проксирует объект из S3/MinIO\n+  - поддерживает `Range: bytes=start-end` (нужно для seek в `<audio>`)\n+\n+## Что заменить при подключении реального TTS\n+\n+В `apps/api/src/worker.ts` заменить блок \"stub TTS generation\" на:\n+- нарезку текста (при необходимости)\n+- вызов провайдера/модели\n+- склейку/нормализацию\n+- сохранение результата в `storageKey`\n+\n+Дополнительно можно:\n+- писать прогресс (`processingPercent`) в отдельную таблицу или в `Audio`.\n+- отдавать статус через polling или SSE/WebSocket.\n+
