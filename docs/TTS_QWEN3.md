# TTS Qwen3 — единственный движок озвучки

В проекте для озвучки книг используется **только TTS Qwen3**. Другие TTS-модели (mock, Coqui и т.п.) не используются.

## Модель: только Base 4-bit (voice clone)

Используется одна модель — **Base 4-bit** для клонирования голоса по WAV:

- **Модель по умолчанию:** `divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit` (переменная окружения `TTS_QWEN3_BASE_MODEL`).
- **Режим:** только синтез по образцу голоса (voice clone). Для каждого запроса нужен WAV: из `storage/voices`, из `voice_sample` в запросе или из настроек голосов.
- **Зависимости для 4-bit:** в окружении должны быть установлены `bitsandbytes>=0.42.0` и `accelerate` (в Docker-образе TTS они уже есть).

## Где лежит и как запускается

- **Путь:** `app/tts_engine_service/` (папка может быть в `.gitignore` и храниться только локально).
- **Запуск из корня проекта:** батник `start-all.bat` сам запускает Qwen3, если найден `app\tts_engine_service\app.py`.
- **Ручной запуск (из папки `app`):**
  ```bat
  cd app
  .venv\Scripts\activate
  python -m tts_engine_service.app
  ```
- **Порт:** по умолчанию **8020** (можно переопределить переменной окружения `TTS_ENGINE_PORT`).

## Контракт сервиса (для Stage4 worker)

Чтобы озвучка работала, сервис должен:

1. **Не завершаться сразу** — процесс должен висеть и слушать порт. В конце `app.py` обязательно должен быть **блокирующий** запуск сервера, например:
   ```python
   if __name__ == "__main__":
       import uvicorn
       port = int(os.environ.get("TTS_ENGINE_PORT", "8020"))
       uvicorn.run(app, host="0.0.0.0", port=port)
   ```
   Без этого процесс сразу выйдет с кодом 0 и в окне будет «Код выхода: 0».

2. **Эндпоинты:**
   - `GET /health` — проверка, что сервис жив (поля `qwen3_base_ready`, `qwen3_base_model` и т.д.);
   - `GET /voices` — список голосов (WAV в `TTS_VOICES_ROOT`);
   - `POST /synthesize` — тело: JSON `{ "text", "speaker", "emotion?", "audio_config?", "voice_sample?" }`; для синтеза нужен образец голоса (speaker → WAV из registry или voice_sample). Ответ: **сырые байты WAV**.

Без WAV для выбранного спикера запрос вернёт 400 (Voice clone required).

**Если POST /synthesize возвращает 503:** откройте `GET http://localhost:8020/health` — в ответе будут `status` (при не загруженной модели — `degraded`), `qwen3_base_ready`, `qwen3_base_error` (причина сбоя загрузки). В консоли, где запущен сервис, при ошибке загрузки модели выводится лог с причиной.

Stage4 worker дергает только этот сервис (`STAGE4_SYNTH_MODE=external`, `EXTERNAL_TTS_URL=http://localhost:8020`). Другие TTS не подключаются.
