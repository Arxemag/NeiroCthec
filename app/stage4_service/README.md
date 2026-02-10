# Stage 4 — Stateless TTS Worker

Отдельный сервис Stage 4 принимает **одну строку** (`Line.original`) и возвращает метаданные аудио.

## Контракт

### POST `/tts`

```json
{
  "task_id": "uuid",
  "user_id": "uuid",
  "book_id": "uuid",
  "line_id": 1834,
  "text": "— Привет, как дела?",
  "speaker": "male",
  "emotion": {
    "energy": 1.2,
    "tempo": 0.95,
    "pitch": -0.1,
    "pause_before": 300,
    "pause_after": 500
  }
}
```

### Response

```json
{
  "task_id": "uuid",
  "status": "DONE",
  "audio_uri": "s3://audio/<user_id>/<book_id>/line_1834.wav",
  "duration_ms": 2840
}
```

## Статусы

- `PENDING`
- `IN_QUEUE`
- `PROCESSING`
- `DONE`
- `ERROR`

## Границы ответственности

Stage 4:
- принимает задачу;
- синтезирует аудио;
- сохраняет WAV в object storage;
- сообщает `DONE/ERROR`.

Stage 4 не хранит состояние книги/пользователя, не знает главы/сегменты и не решает судьбу пайплайна.

## Внутренняя модель параллелизма

- HTTP endpoint кладёт задачи в `asyncio.Queue`.
- Worker(ы) забирают задачи из очереди.
- `asyncio.Semaphore` ограничивает количество параллельных GPU-задач.

## Запуск

```bash
docker compose -f app/docker-compose.yml up --build stage4-tts
```
