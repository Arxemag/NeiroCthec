# TTS_Qwen3_Engine_Module — Техническое задание

## Назначение и ответственность

- **Что делает модуль**:
  - Предоставляет HTTP API для синтеза речи (text → WAV) с voice clone по WAV образцу.
  - Управляет загрузкой модели, выбором устройства (GPU/CPU), кэшем voice-clone prompt.
- **Что модуль НЕ делает**:
  - Не знает про книги/проекты/пайплайн.
  - Не хранит SoT (только читает WAV образцы из выделенного storage location).

## Границы и зависимости

- **Код (as-is)**: `app/tts_engine_service/app.py`
- **Вход**: HTTP `POST /synthesize` / `POST /synthesize-batch`
- **Выход**: WAV bytes (response body) + headers (duration/backend).
- **Зависимости**:
  - GPU/CPU runtime (PyTorch, CUDA/ROCm при необходимости).
  - Voice samples directory (as-is `storage/voices`).

## Публичные контракты (as-is)

См. `docs/TTS_QWEN3.md` и реализацию endpoints:
- `GET /health`
- `GET /voices`
- `POST /synthesize`
- `POST /synthesize-batch`

### `POST /synthesize`

Request JSON (минимум):
- `text: string`
- `speaker: string` (например narrator/male/female)
- `emotion?: { energy?: number, tempo?: number, pitch?: number }`
- `audio_config?: object`
- `voice_sample?: string` (путь/ссылка на WAV, если нет speaker в registry)
- `speaker_wav_path?: string` (имеет приоритет)

Response:
- `200 audio/wav` (raw bytes)
- headers: `x-duration-ms`, `x-tts-backend`, etc.

Ошибки:
- `400` если нет доступного WAV для voice clone
- `503` если модель не готова (health status degraded/ошибка загрузки)

## Target требования

- **Стабильность контракта**: response всегда WAV, ошибки — JSON с понятным detail.
- **Ограничения**: max text length, batch size (<=16), rate limits (опционально).
- **Наблюдаемость**: логировать requestId/taskId (если передан), latency, device.

## Конфигурация (as-is)

Ключевые переменные окружения:
- `TTS_ENGINE_PORT` (default 8020)
- `TTS_BACKEND` (qwen3/auto/mock/espeak)
- `TTS_DEVICE` (auto/cuda/cpu), `TTS_USE_GPU`
- `TTS_QWEN3_BASE_MODEL`
- `TTS_VOICES_ROOT`
- `TTS_VOICE_CLONE_CACHE_MAX`

## Критерии приёмки

- [x] `GET /health` показывает readiness и причину деградации.
- [x] `POST /synthesize` синтезирует WAV при наличии voice sample.

