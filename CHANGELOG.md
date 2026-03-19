# Changelog

## 2026-03-18

- Core ↔ TaskRegistry (NestJS) integration:
  - Added `RenderTask` SoT model in Prisma (`taskId`, `clientId`, `bookId`, `lineId`, `engine`, status, `storageKey`).
  - Implemented NestJS `TaskRegistry` internal endpoints for task lifecycle (`upsert/complete/fail/list` + `getOne`).
  - Updated Core (`app_pipeline.py`) to generate deterministic `taskId` per `(clientId, bookId, line_id, text/voice/emotion/audio_config/engine)` and to upsert/complete tasks via TaskRegistry.
  - Added Core read-API endpoints:
    - `GET /tasks/{taskId}` — status + metadata
    - `GET /artifacts/{taskId}` — WAV from `storageKey` (локально, пока без S3)
  - Updated Stage4 worker to mark tasks as `DONE`/`FAILED` in TaskRegistry.

- Queue Core → Stage4 via Redis Stream:
  - Added Redis Stream publish/consume mode (`TTS_USE_REDIS_QUEUE=1`) for TTS tasks.
  - Core publishes render tasks to `tts.render.v1`; Stage4 consumes via consumer group (`TTS_STAGE4_CONSUMER_GROUP`), performs synth, then ack’ает message.
  - Added `redis` dependency to Core container requirements.

- UI-target behavior (“full_first”):
  - Core now auto-assembles `final.wav` and ready `chapter_*.wav` as soon as all lines for a book are present in `done`.

- Infrastructure:
  - Updated `docker-compose.yml` with Redis Stream env vars for Core and Stage4.

- Storage conventions (S3/MinIO, MVP):
  - Stage4 теперь при наличии S3 env загружает готовые line WAV в `stage4/tasks/<clientId>/<taskId>.wav` и сохраняет этот `storageKey` в `RenderTask`.
  - Core: `GET /artifacts/{taskId}` теперь, если локальный файл по `storageKey` не найден, отдаёт signed URL на MinIO (Redirect).
  - Добавлены `boto3` зависимости для Core/Stage4.

- Stage5 assembler (final/chapter) → S3 + metadata:
  - Добавлена Prisma/SoT модель `RenderAssembly` и эндпоинты TaskRegistry для сборок.
  - Core при сборке `final.wav` и `chapter_*.wav`:
    - вычисляет детерминированный `assemblyId` по ordered `taskId`,
    - загружает артефакт в MinIO по `stage5/assemblies/<clientId>/<assemblyId>/...`,
    - пишет `storageKey/durationMs` в Postgres через TaskRegistry.
  - Core read-API:
    - `GET /books/:id/download` и `GET /books/:id/chapters/:num` отдают signed URL из S3, если локальные файлы отсутствуют.

- Restartable statuses:
  - Core теперь, если in-memory state отсутствует после рестарта, определяет `GET /books/:id` и `GET /books/:id/status` по SoT из TaskRegistry (`RenderTask` + `RenderAssembly`).

- Restartable `chapters_ready`:
  - Расширена `RenderTask` (Prisma) полем `chapterId`.
  - Core сохраняет `chapterId` при постановке задач в TaskRegistry и теперь вычисляет `chapters_ready` после рестарта по completed `done` задачам из Postgres.

- Restartable Stage5 (final/chapter) — вариант А:
  - Расширена `RenderTask` persisted-структурой строки для пересборки после рестарта (`speaker`, `lineType`, `emotion`, `isChapterHeader`).
  - Core научился собирать `final.wav` и `chapter_*.wav` из `RenderTask` + `storageKey` (скачивает line WAV в temp), когда in-memory `_book_states` отсутствует.

- Persisted сегменты для корректного порядка Stage5 после рестартов:
  - Расширена `RenderTask` сегментными полями (`isSegment`, `baseLineId`, `segmentIndex`, `segmentTotal`).
  - Core сохраняет сегментную мета-информацию при XTTS-разбиении и Stage5Assembler теперь сортирует сегменты по `base_line_id/segment_index` (без heuristics по `line_id >= 1000`).

- Prisma:
  - Сгенерирована и применена migration для таблицы `RenderTask`.

- Contract-валідации pipeline:
  - Stage1 (`StructuralParser`): добавлена строгая проверка инвариантов `UserBookFormat/Line` перед stage2.
  - Stage2 (`stage2_post_chunk`): проверка `speaker ∈ {narrator,male,female}`, `chapter_id >= 1`, детерминированный последовательный `idx`, ограничение длины чанков.
  - Stage3: подтвержден clamp `tempo/pitch` (runtime-проверка после `EmotionResolver`).

- Stage4 (Redis Stream) Reliability/Observability:
  - Добавлен DLQ stream (`TTS_DLQ_STREAM`, по умолчанию `tts.render.v1.dlq`) и отправка проблемных сообщений в DLQ при failure.
  - Failure-лог усилен: в логах всегда присутствуют `taskId/clientId/book_id/line_id/engine/latencyMs/durationMs`.

- Core API: отдача артефактов через S3 в приоритете:
  - `GET /books/:id/download` и `GET /books/:id/chapters/:num` сначала пробуют `RenderAssembly.storageKey` из TaskRegistry и делают `Redirect` на presigned URL; локальный `FileResponse` остаётся как fallback.

- Website/Nest API:
  - Добавлен `TasksProxyModule` (Nest): `GET /api/tasks/:taskId` и `GET /api/tasks/:taskId/artifact` проксируют в Core по `taskId`.

- Multi-chapter verification:
  - Проверено, что `chapterId=2` для книг с несколькими главами редиректит на presigned URL и `RenderAssembly` существует в TaskRegistry.

