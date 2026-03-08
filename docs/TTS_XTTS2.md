# TTS XTTS2 (Coqui)

Сервис озвучки на **Coqui XTTS v2** работает **только в Docker** — контейнер `tts-xtts`, порт **8021**. Контракт совместим с Qwen3: `POST /synthesize` (text, speaker, speaker_wav_path, audio_config) → WAV.

## Запуск

XTTS2 входит в стандартный пул контейнеров. При запуске из корня проекта:

```bat
docker compose up -d
```

поднимается в том числе сервис **tts-xtts** (образ из `Dockerfile.xtts`). Stage4 обращается к нему по `EXTERNAL_TTS_XTTS_URL=http://tts-xtts:8021` (значение задаётся в `docker-compose.yml`).

Требуется **NVIDIA GPU** и [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

При первом запуске контейнера модель XTTS v2 скачивается в volume (порядка 1.5–2 ГБ); в это время запросы к `POST /synthesize` могут возвращать **503**. Дождитесь окончания загрузки в логах (`docker compose logs -f tts-xtts`) и проверьте `GET /health` — при `xtts_ready: true` синтез будет отвечать 200.

**Если модель уже скачана («is already downloaded»), но 503 не пропадает:** проверьте ответ `GET /health` — в нём есть поля `xtts_ready`, `xtts_error`, `xtts_loading`. Если `xtts_error` не пустое — загрузка в память упала (например, нехватка GPU-памяти или ошибка CUDA). Просмотрите полные логи: `docker compose logs tts-xtts 2>&1 | tail -80` — после строки «already downloaded» может быть traceback. Загрузка модели в GPU может занимать 1–2 минуты; несколько первых запросов подряд могут получать 503, пока модель не поднимется в память — подождите и повторите запрос или проверьте health.

## Контракт

- **GET /health** — статус (xtts_ready, xtts_error, xtts_loading).
- **GET /voices** — список голосов (id, path) из общего реестра `core.voices`.
- **POST /synthesize** — JSON: `text`, `speaker`, опционально `speaker_wav_path`, `audio_config` (в т.ч. `language`). Ответ: сырые байты WAV. Если передан `speaker_wav_path`, он используется как образец голоса; иначе путь берётся по `speaker` из `storage/voices`.

Голоса — те же WAV в `storage/voices` (narrator, male, female и кастомные), что и для Qwen3.

## Переменные окружения (контейнер)

- `COQUI_TOS_AGREED=1` — принять лицензию Coqui неинтерактивно (в Docker нет stdin; задаётся в Dockerfile и compose).
- `TTS_ENGINE_PORT` — порт (по умолчанию 8021).
- `TTS_USE_GPU` — `true`/`false`. Если в `/health` видите `xtts_error: "CUDA is not availabe on this machine."`, задайте `TTS_USE_GPU=false` в окружении контейнера — модель поднимется на CPU (медленнее, но синтез будет работать). В `docker-compose.yml` по умолчанию выставлено `false` для совместимости с машинами без NVIDIA.
- `TTS_XTTS_LOG_LEVEL` — уровень логирования.

Stage4 при выборе пользователем движка XTTS2 обращается по `EXTERNAL_TTS_XTTS_URL` (в compose по умолчанию `http://tts-xtts:8021`).
