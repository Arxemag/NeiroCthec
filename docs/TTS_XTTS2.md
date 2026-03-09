# TTS XTTS2 (Coqui)

Сервис озвучки на **Coqui XTTS v2** работает **только в Docker** — контейнер `tts-xtts`, порт **8021**. Контракт совместим с Qwen3: `POST /synthesize` (text, speaker, speaker_wav_path, audio_config) → WAV.

## Запуск

XTTS2 входит в стандартный пул контейнеров. При запуске из корня проекта:

```bat
docker compose up -d
```

поднимается в том числе сервис **tts-xtts** (образ из `Dockerfile.xtts`). Stage4 обращается к нему по `EXTERNAL_TTS_XTTS_URL=http://tts-xtts:8021` (значение задаётся в `docker-compose.yml`).

Требуется **NVIDIA GPU** и [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

При старте контейнера модель загружается в память **до** того, как сервер начнёт принимать запросы (ожидание до 5 мин в lifespan). Поэтому первые запросы не должны получать 503 из‑за «модель не загружена». Если модель ещё скачивается в volume при первом запуске — дождитесь в логах «is already downloaded» и «XTTS v2 loaded». Stage4 при ответе 503 от tts-xtts повторяет запрос до 5 раз с паузой 20 с (переменные `STAGE4_TTS_503_RETRIES`, `STAGE4_TTS_503_RETRY_DELAY_SEC`).

**Если модель уже скачана («is already downloaded»), но 503 не пропадает:** проверьте ответ `GET /health` — в нём есть поля `xtts_ready`, `xtts_error`, `xtts_loading`. Если `xtts_error` не пустое — загрузка в память упала (например, нехватка GPU-памяти или ошибка CUDA). Просмотрите полные логи: `docker compose logs tts-xtts 2>&1 | tail -80` — после строки «already downloaded» может быть traceback. Загрузка модели в GPU может занимать 1–2 минуты; несколько первых запросов подряд могут получать 503, пока модель не поднимется в память — подождите и повторите запрос или проверьте health.

## Контракт

- **GET /health** — статус (xtts_ready, xtts_error, xtts_loading).
- **GET /voices** — список голосов (id, path) из общего реестра `core.voices`.
- **POST /synthesize** — JSON: `text`, `speaker`, опционально `speaker_wav_path`, `audio_config` (в т.ч. `language`, `temperature`, `speed`, `split_sentences`). Ответ: сырые байты WAV. Если передан `speaker_wav_path`, он используется как образец голоса; иначе путь берётся по `speaker` из `storage/voices`. Перед синтезом текст нормализуется (тире, точка в конце), чтобы снизить артифакты и «озвучивание» пунктуации.

Голоса — те же WAV в `storage/voices` (narrator, male, female и кастомные), что и для Qwen3.

## Переменные окружения (контейнер)

- `COQUI_TOS_AGREED=1` — принять лицензию Coqui неинтерактивно (в Docker нет stdin; задаётся в Dockerfile и compose).
- `TTS_ENGINE_PORT` — порт (по умолчанию 8021).
- `TTS_USE_GPU` — `true`/`false`. Если в `/health` видите `xtts_error: "CUDA is not availabe on this machine."`, задайте `TTS_USE_GPU=false` в окружении контейнера — модель поднимется на CPU (медленнее, но синтез будет работать). В `docker-compose.yml` по умолчанию выставлено `false` для совместимости с машинами без NVIDIA.
- `TTS_XTTS_TEMPERATURE` — температура инференса (по умолчанию 0.35; ниже — меньше артифактов).
- `TTS_XTTS_SPEED` — скорость речи (по умолчанию 1.0).
- `TTS_XTTS_SPLIT_SENTENCES` — разбивать текст по предложениям (по умолчанию true).
- `TTS_XTTS_LOG_LEVEL` — уровень логирования.
- `TTS_XTTS_SINGLE_CHUNK` — если `1`/`true`/`yes`, текст не разбивается на чанки, один вызов `tts_to_file` (как до введения чанкинга). Используйте для проверки, не связана ли ошибка с чанкингом/склейкой.

Stage4 при выборе пользователем движка XTTS2 обращается по `EXTERNAL_TTS_XTTS_URL` (в compose по умолчанию `http://tts-xtts:8021`).

**XTTS на CPU:** один запрос может занимать **1–3 минуты** на одну строку. Причины: (1) первый запрос после старта может включать дозагрузку модели в память (десятки секунд); (2) сам инференс на CPU медленный — каждый чанк текста 30–90+ секунд. В логах tts-xtts после запроса появятся строки `synthesize request: ...`, `chunk 1/N done in X.Xs`, `synthesize done in X.Xs` — по ним видно, сколько ушло на загрузку модели и на синтез по чанкам. В `docker-compose.yml` для stage4 задано `EXTERNAL_TTS_TIMEOUT_SEC=300` и `replicas: 1`. Для ускорения нужен GPU (NVIDIA + Container Toolkit, `TTS_USE_GPU=true`).
