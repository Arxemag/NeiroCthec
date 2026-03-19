# TTS_XTTS2_Engine_Module — Техническое задание

## Назначение и ответственность

- **Что делает модуль**:
  - Предоставляет HTTP API для синтеза речи (text → WAV) на базе Coqui XTTS v2.
  - Поддерживает параметры качества/скорости и выбор образца голоса.
- **Что модуль НЕ делает**:
  - Не управляет очередями/задачами.
  - Не владеет доменными сущностями.

## Границы и зависимости

- **Код (as-is)**: `app/tts_engine_xtts/*`
- **Использование**: Stage4 выбирает XTTS2 по `tts_engine="xtts2"` (as-is).
- **Зависимости**:
  - Обычно NVIDIA GPU + container toolkit (as-is: docker).
  - Voice samples (WAV) из общего registry (`storage/voices`).

## Публичные контракты (as-is)

См. `docs/TTS_XTTS2.md`.

Ожидаемые endpoints:
- `GET /health`
- `GET /voices`
- `POST /synthesize` → WAV bytes

## Нефункциональные требования

- **Долгие запросы**: первый запрос может быть долгим (загрузка модели), далее — стабильно.
- **503 при загрузке**: Stage4 должен уметь ограниченно ретраить 503.

## Конфигурация (as-is)

Ключевые переменные:
- `TTS_ENGINE_PORT` (default 8021)
- `TTS_USE_GPU`
- `TTS_XTTS_NORMALIZE_TEXT`
- Параметры качества (temperature/speed и др.)

## Критерии приёмки

- [x] `/health` отражает `xtts_ready/xtts_loading/xtts_error`.
- [x] `/synthesize` возвращает валидный WAV.

