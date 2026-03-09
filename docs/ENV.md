# Переменные окружения

| Переменная | Где | Описание |
|------------|-----|----------|
| DATABASE_URL | api, worker | PostgreSQL URL (postgresql://neuro:neuro@postgres:5432/neurochtec?schema=public) |
| APP_API_URL | api | URL Core API (http://core:8000) |
| NEXT_PUBLIC_APP_API_URL | web | `proxy` или URL Core для браузера |
| API_PROXY_TARGET | web | URL Nest API для прокси /api/* (http://api:4000) |
| APP_API_PROXY_TARGET | web | URL Core для прокси /app-api/* (http://core:8000) |
| EXTERNAL_TTS_XTTS_URL | stage4 | URL TTS XTTS (http://tts-xtts:8021) |
| EXTERNAL_TTS_XTTS_TIMEOUT_SEC | stage4 | Таймаут запроса к XTTS (сек), по умолчанию 600 |
| TTS_USE_GPU | tts-xtts | true/false — использование GPU для XTTS |
| APP_STAGE4_URL | core | URL stage4 для превью (http://stage4:8001) |
| CORE_INTERNAL_URL | stage4 | URL Core internal API (http://core:8000/internal) |
| S3_ENDPOINT | api, worker | MinIO (http://minio:9000) |
| REDIS_URL | api, worker | Redis (redis://redis:6379) |
