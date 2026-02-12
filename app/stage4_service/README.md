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

## Режимы синтеза

`stage4-tts` теперь поддерживает два режима:
- `STAGE4_SYNTH_MODE=mock` — локальный генератор WAV внутри контейнера (режим по умолчанию).
- `STAGE4_SYNTH_MODE=external` — проксирование синтеза в отдельный HTTP TTS-сервис.

Для внешнего режима нужны переменные:
- `EXTERNAL_TTS_URL` (по умолчанию `http://tts-engine:8020`)
- `EXTERNAL_TTS_TIMEOUT_SEC` (по умолчанию `60`)

## Статусы

- `PENDING`
- `IN_QUEUE`
- `PROCESSING`
- `DONE`
- `ERROR`

## Границы ответственности

Stage 4:
- принимает задачу;
- отправляет задачу в выбранный backend синтеза;
- сохраняет WAV в object storage;
- сообщает `DONE/ERROR`.

Stage 4 не хранит состояние книги/пользователя, не знает главы/сегменты и не решает судьбу пайплайна.

## Запуск

```bash
docker compose -f app/docker-compose.yml up --build stage4-tts tts-engine
```


### Почему в проекте 2 TTS-сервиса
Это нормально и задумано архитектурой:
- `stage4-tts` — orchestration/worker (берёт задачи, сохраняет файлы, отдаёт статус).
- `tts-engine` — собственно движок синтеза (Coqui/espeak/mock).

Проблема возникает, когда `tts-engine` уходит в деградированный backend (`espeak`/`mock`) и это не видно сразу.
Для защиты добавлены переменные в `stage4-tts`:
- `STAGE4_ENFORCE_TTS_BACKEND=false` (рекомендуется для dev, чтобы не блокировать пайплайн при деградации backend)
- `STAGE4_EXPECT_TTS_BACKEND=coqui`

`stage4-tts` проверяет HTTP-заголовок `x-tts-backend` от `tts-engine` и вернёт ошибку, если backend не совпадает с ожидаемым.


### Если видите 502 на `/internal/process-book-stage4`
Частая причина: `tts-engine` не может поднять Coqui и в строгом режиме stage4 блокирует задачу.
Проверьте `GET /health` у `tts-engine` и включите мягкий режим (`STAGE4_ENFORCE_TTS_BACKEND=false`) для непрерывной обработки.
