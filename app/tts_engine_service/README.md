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
- `TTS_BACKEND=coqui|espeak|mock|auto` (для production качества рекомендуется `coqui`)
- `TTS_USE_GPU=true|false` — попросить Coqui использовать GPU
- `TTS_REQUIRE_GPU=true|false` — fail-fast: если CUDA недоступна или Coqui не смог подняться на GPU, `/synthesize` вернёт `503`
- `TTS_COQUI_GPU_FALLBACK_CPU=true|false` — если инициализация Coqui на GPU упала, попробовать подняться на CPU
- `TTS_COQUI_TOS_ACCEPTED=true|false` — авто-принятие Coqui CPML в non-interactive среде (ставит `COQUI_TOS_AGREED=1`)
- `TTS_HOME=/srv/storage/tts_cache` — кэш моделей Coqui (рекомендуется вынести в persistent volume)
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

- Относительные `voice_sample` пути вида `storage/...` автоматически нормализуются через `SHARED_STORAGE_ROOT` (по умолчанию `/srv/storage`).


### Рекомендуемый production-профиль качества
- `TTS_BACKEND=coqui`
- `TTS_USE_GPU=true`
- `TTS_REQUIRE_GPU=false`
- `TTS_COQUI_GPU_FALLBACK_CPU=true`
- `TTS_ALLOW_DEGRADED_BACKEND=false`
- `STAGE4_ENFORCE_TTS_BACKEND=true`

Такой профиль запрещает тихие деградации в `espeak/mock`; при проблемах инициализации GPU Coqui сохранит качество движка через CPU fallback вместо аварийного 503.


### Важно про ошибку `EOF when reading a line`
Если видите интерактивный prompt Coqui про лицензию в Docker, включите `TTS_COQUI_TOS_ACCEPTED=true` (или вручную `COQUI_TOS_AGREED=1`). Иначе Coqui попытается вызвать `input()` и упадёт в non-interactive контейнере.


Дополнительно, сервис перехватывает интерактивный prompt Coqui и при `TTS_COQUI_TOS_ACCEPTED=true` автоматически отвечает `y`, чтобы избежать `EOFError` в Docker.
