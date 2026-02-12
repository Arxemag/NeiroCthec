# Standalone TTS Engine

Минимальный HTTP-сервис TTS, который можно запускать отдельно от core-пайплайна.

## API
- `GET /health`
- `POST /synthesize`

### Пример `POST /synthesize`
```json
{
  "text": "Привет, это тест",
  "speaker": "narrator",
  "emotion": {"energy": 1.0, "tempo": 1.0, "pitch": 0.0}
}
```

Возвращает `audio/wav` и заголовок `x-duration-ms`.

## Бэкенды синтеза
- Если установлен `TTS` (Coqui), сервис использует реальный синтезатор и voice samples из `storage/voices/{narrator,male,female}.wav`.
- Если Coqui недоступен, включается mock-tone fallback (для контрактной отладки).

`GET /health` возвращает активный backend в поле `backend` (`coqui` или `mock`).


## Переменные окружения
- `TTS_BACKEND=coqui|mock|auto` (рекомендуется `coqui`, чтобы не получить тон-генератор).
- `TTS_LANGUAGE=ru`
- `TTS_VOICES_ROOT=/srv/storage/voices`

`/health` показывает `requested_backend`, `active_backend` и `coqui_error` для диагностики.
