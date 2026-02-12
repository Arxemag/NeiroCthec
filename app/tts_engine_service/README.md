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
- `coqui` — основной прод-режим (XTTS/Coqui).
- `espeak` — деградированный fallback (может давать сильный акцент/низкую разборчивость).
- `mock` — тестовый тональный синтезатор.
- `auto` — пытается Coqui; если Coqui не поднялся, по умолчанию возвращает ошибку `503`.

`GET /health` возвращает `requested_backend`, `active_backend`, `coqui_ready`, `coqui_error`.

## Важно для XTTS
- Для `xtts_v2` обязателен `speaker_wav` (образец голоса).
- Метки speaker нормализуются (`famaly`/`femaly` → `female`, неизвестные значения → `narrator`).
- Если образец не найден (`voice_sample` в запросе и/или файлы в `TTS_VOICES_ROOT`), сервис вернёт `422`, а не будет синтезировать "чужим" голосом.

## Переменные окружения
- `TTS_BACKEND=coqui|espeak|mock|auto` (для dev/стабильности пайплайна рекомендуется `auto`)
- `TTS_LANGUAGE=ru`
- `TTS_VOICES_ROOT=/srv/storage/voices`
- `TTS_ALLOW_DEGRADED_BACKEND=false|true`
  - `false` (по умолчанию): в `auto` режиме при недоступном Coqui отдаём `503`
  - `true`: разрешает fallback в `espeak`/`mock`

`/health` используйте для быстрой проверки, что реально активен именно `coqui`.


Для production качества лучше закрепить `TTS_BACKEND=coqui` и проверить, что Coqui и voice samples корректно доступны.

- Для XTTS учитывается `audio_config.xtts.speed_base` (умножается на `emotion.tempo`, итог clamp 0.5..2.0).

- В ответе `/synthesize` для Coqui добавляются debug-заголовки: `x-tts-language`, `x-tts-speaker`, `x-tts-speaker-wav`.
- Для XTTS также применяются параметры из `audio_config.xtts`: `temperature`, `top_k`, `top_p`, `repetition_penalty`.
