# Standalone TTS Engine

Качественный HTTP-сервис TTS с поддержкой AMD (ROCm) и NVIDIA (CUDA), стабильной работой и возможностью замены спикеров.

## API
- `GET /health` — статус сервиса, backend, GPU, количество голосов
- `GET /voices` — список доступных голосов (ID, путь, источник)
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

## Поддержка GPU (AMD и NVIDIA)
- **NVIDIA**: установите PyTorch с CUDA (`pip install torch --index-url https://download.pytorch.org/whl/cu121`)
- **AMD**: установите PyTorch с ROCm (`pip install torch --index-url https://download.pytorch.org/whl/rocm5.6`)
- ROCm: проверяется через `torch.cuda` (API-совместимо) и fallback на `torch.hip.is_available()`
- При ошибке инициализации GPU — автоматический fallback на CPU (если `TTS_COQUI_GPU_FALLBACK_CPU=true`)
- `TTS_DEVICE=auto|cuda|cpu` — принудительный выбор устройства
- `TTS_REQUIRE_GPU=true` — отдавать 503, если GPU недоступен

### Проверка использования AMD GPU
- `GET /health` возвращает `gpu_vendor: "amd"` при работе на AMD Radeon (ROCm)
- `cuda_device` содержит имя видеокарты (напр. `AMD Radeon RX 6800 XT`)
- `coqui_device: "cuda"` — Coqui использует GPU
- При синтезе в логах: `coqui synthesize: device=cuda gpu_vendor=amd gpu_name=...`
- В ответе `/synthesize` — заголовки `x-tts-device: cuda`, `x-tts-gpu-vendor: amd`

### Docker с AMD ROCm
- `docker-compose -f docker-compose.yml -f docker-compose.rocm.yml up -d` — TTS на AMD GPU
- Требуется Linux с ROCm и устройствами `/dev/kfd`, `/dev/dri`

## Замена и расширение спикеров
Голоса можно менять тремя способами:

1. **Добавить .wav в `TTS_VOICES_ROOT`** — имя файла без расширения станет ID спикера (например, `hero.wav` → `hero`)
2. **Файл `voices.yaml`** в каталоге голосов — явное сопоставление `id: путь` (см. `voices.yaml.example`)
3. **В запросе** — `voice_sample` или `audio_config.voices`

Приоритет: запрос > config > discovered > builtin. Встроенные `narrator`, `male`, `female` можно переопределить.

**Алиасы** в `voices.yaml` — секция `aliases:` позволяет задать синонимы (например, `woman` → `female`). Есть встроенные: famaly→female, man→male, main→narrator и др.

## Переменные окружения
- `TTS_BACKEND=coqui|espeak|mock|auto` (рекомендуется `auto`)
- `TTS_LANGUAGE=ru`
- `TTS_VOICES_ROOT=/srv/storage/voices`
- `TTS_USE_GPU=true` — использовать GPU, если доступен
- `TTS_ALLOW_DEGRADED_BACKEND=false|true`
  - `false`: в `auto` при недоступном Coqui отдаём `503`
  - `true`: разрешает fallback в `espeak`/`mock`
- `COQUI_TOS_AGREED=1` — принять лицензию Coqui без интерактива
- `TTS_HOME=/srv/storage/tts_cache` — кэш моделей

`/health` и `/voices` используйте для проверки backend и списка голосов.


Для production качества лучше закрепить `TTS_BACKEND=coqui` и проверить, что Coqui и voice samples корректно доступны.

- Для XTTS учитывается `audio_config.xtts.speed_base` (умножается на `emotion.tempo`, итог clamp 0.5..2.0).
- Дефолтные XTTS-параметры при отсутствии в config: temperature=0.7, top_k=50, top_p=0.9, repetition_penalty=2.0.

- В ответе `/synthesize` для Coqui добавляются debug-заголовки: `x-tts-language`, `x-tts-speaker`, `x-tts-speaker-wav`.
- Для XTTS также применяются параметры из `audio_config.xtts`: `temperature`, `top_k`, `top_p`, `repetition_penalty`.

- Относительные `voice_sample` пути вида `storage/...` автоматически нормализуются через `SHARED_STORAGE_ROOT` (по умолчанию `/srv/storage`).
