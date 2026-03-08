# TTS XTTS2 (Coqui)

Сервис озвучки на **Coqui XTTS v2** работает **только в Docker** — контейнер `tts-xtts`, порт **8021**. Контракт совместим с Qwen3: `POST /synthesize` (text, speaker, speaker_wav_path, audio_config) → WAV.

## Запуск

XTTS2 входит в стандартный пул контейнеров. При запуске из корня проекта:

```bat
docker compose up -d
```

поднимается в том числе сервис **tts-xtts** (образ из `Dockerfile.xtts`). Stage4 обращается к нему по `EXTERNAL_TTS_XTTS_URL=http://tts-xtts:8021` (значение задаётся в `docker-compose.yml`).

Требуется **NVIDIA GPU** и [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

## Контракт

- **GET /health** — статус (xtts_ready, xtts_error, xtts_loading).
- **GET /voices** — список голосов (id, path) из общего реестра `core.voices`.
- **POST /synthesize** — JSON: `text`, `speaker`, опционально `speaker_wav_path`, `audio_config` (в т.ч. `language`). Ответ: сырые байты WAV. Если передан `speaker_wav_path`, он используется как образец голоса; иначе путь берётся по `speaker` из `storage/voices`.

Голоса — те же WAV в `storage/voices` (narrator, male, female и кастомные), что и для Qwen3.

## Переменные окружения (контейнер)

- `TTS_ENGINE_PORT` — порт (по умолчанию 8021).
- `TTS_USE_GPU` — `true`/`false` (по умолчанию `true` для CUDA).
- `TTS_XTTS_LOG_LEVEL` — уровень логирования.

Stage4 при выборе пользователем движка XTTS2 обращается по `EXTERNAL_TTS_XTTS_URL` (в compose по умолчанию `http://tts-xtts:8021`).
