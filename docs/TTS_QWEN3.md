# TTS Qwen3 — единственный движок озвучки

В проекте для озвучки книг используется **только TTS Qwen3**. Другие TTS-модели (mock, Coqui и т.п.) не используются.

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
   - `GET /health` — проверка, что сервис жив;
   - `GET /voices` — список голосов (по желанию);
   - `POST /synthesize` — тело: JSON `{ "text", "speaker", "emotion?", "audio_config?" }`, ответ: **сырые байты WAV** (Stage4 worker так и ожидает).

Stage4 worker дергает только этот сервис (`STAGE4_SYNTH_MODE=external`, `EXTERNAL_TTS_URL=http://localhost:8020`). Другие TTS не подключаются.
