# NeiroCthec — Внутренняя архитектура (API Core + Stage4 Worker)

Документ описывает **внутренний контракт системы** для backend, frontend и mobile команд.

---

## 1) Общая схема сервисов

Система разделена на 3 сервиса:

1. **api** (FastAPI, CPU)
   - публичные роуты книг;
   - внутренние роуты для взаимодействия со Stage4;
   - оркестрация Stage0–Stage3 и Stage5;
   - работа с PostgreSQL.
2. **stage4-tts** (FastAPI worker, отдельный контейнер)
   - берёт TTS-задачи из Core через `/internal/tts-next`;
   - генерирует WAV;
   - подтверждает результат через `/internal/tts-complete`.
3. **postgres**
   - единственный источник состояния (book/line/task статусы).

Compose-расклад:
- `api` собирается из `Dockerfile.api`.
- `stage4-tts` собирается из `stage4_service/Dockerfile`.
- `postgres` поднимается отдельным сервисом с healthcheck.

---

## 2) Pipeline и стадии

Pipeline на уровне строки (Line):

1. **Stage0** — загрузка source-файла в строки (`Line`), первичное определение типа (`dialogue`/`narrator`).
2. **Stage1** — структурный проход (`new -> stage1_done`).
3. **Stage2** — нормализация контракта строки:
   - `type`
   - `speaker`
   - `segments`
   (`stage1_done -> stage2_done`).
4. **Stage3** — проставление `emotion` и постановка TTS-задачи (`TTSTask`) в статус `pending` (`stage2_done -> tts_pending`).
5. **Stage4** — отдельный сервис TTS (генерация WAV).
6. **Stage5** — сборка финального артефакта книги, когда все строки получили `tts_done`.

### Важные свойства

- Стадии работают через **статусы в БД**, а не прямые вызовы друг друга.
- Stage0 реализован идемпотентно: повторный запуск не дублирует строки, если они уже есть.
- Stage3 публикует задачи только если у строки ещё нет `tts_task`.

---

## 3) Модели данных (для фронта/мобилы)

## Book

- `id` (UUID строкой)
- `user_id`
- `title`
- `source_path`
- `final_audio_path`
- `status`: `uploaded | parsing | analyzed | tts_processing | assembling | completed | error`
- `created_at`, `updated_at`

## Line

- `id` (UUID строкой)
- `book_id`
- `idx`
- `type`
- `speaker`
- `original`
- `segments` (JSON)
- `emotion` (JSON)
- `tts_status`: `new | stage1_done | stage2_done | stage3_done | tts_pending | tts_done | assembled | error`
- `audio_path`
- `created_at`, `updated_at`

## TTSTask

- `id`
- `line_id` (unique)
- `payload` (line/user/book/text/voice/emotion)
- `status`: `pending | processing | done | error`
- `created_at`, `updated_at`

---

## 4) Публичный API (для web/mobile)

Базовый префикс: `/books`

1. `POST /books/upload`
   - multipart (`file`)
   - создаёт книгу, запускает Stage0–Stage3 оркестрацию.

2. `GET /books`
   - список книг текущего пользователя.

3. `GET /books/{book_id}`
   - карточка книги.

4. `DELETE /books/{book_id}`
   - удаление книги.

5. `GET /books/{book_id}/status`
   - агрегированный прогресс:
     - `stage`
     - `progress`
     - `total_lines`
     - `tts_done`

6. `GET /books/{book_id}/download`
   - скачивание финального MP3, если готов.

### Авторизация / изоляция

Во всех пользовательских ручках используется заголовок:
- `X-User-Id`

Это обязательный идентификатор пользователя для фильтрации по `user_id`.

---

## 5) Внутренний API (Core <-> Stage4)

Базовый префикс: `/internal`

1. `POST /internal/tts-next`
   - Stage4 запрашивает следующую pending-задачу;
   - Core переводит task в `processing` и возвращает payload.

2. `POST /internal/tts-complete`
   - Stage4 сообщает `line_id` + `audio_path`;
   - Core переводит строку в `tts_done`, task в `done`, проверяет Stage5.

3. `POST /internal/retry-line`
   - сброс строки в `tts_pending` + task в `pending`.

4. `POST /internal/retry-book`
   - повторный прогон пайплайна по книге.

---

## 6) Stage4 как отдельный сервис

Stage4 Worker предоставляет:

- `GET /health`
- `POST /tts` — синтез одной строки
- `POST /process-next` — pull-модель: взять задачу у Core, синтезировать, отправить complete callback

### Контракт TTSRequest

- `task_id`
- `user_id`
- `book_id`
- `line_id`
- `text`
- `speaker`
- `emotion`

### Контракт TTSResponse

- `task_id`
- `status` (`DONE/ERROR/...`)
- `audio_uri`
- `duration_ms`
- `error`

---

## 7) Карта статусов для UI

Рекомендуемая интерпретация статусов в интерфейсе:

- `uploaded/parsing/analyzed` — подготовка текста.
- `tts_processing` — идёт генерация аудио строк.
- `assembling` — финальная сборка.
- `completed` — доступна кнопка download.
- `error` — показать retry (`retry-line`/`retry-book`).

`/books/{id}/status` можно использовать как основной endpoint прогресса для прогресс-баров.

---

## 8) Что важно фронту и мобиле

1. Система **state-based**: не ждать синхронного результата после upload.
2. После upload нужно периодически опрашивать:
   - `GET /books/{id}/status`
   - `GET /books/{id}`
3. При `completed` открывать `GET /books/{id}/download`.
4. Все вызовы делать с `X-User-Id`, иначе 401.
5. Stage4 полностью скрыт от клиента — с ним работает только Core.

---

## 9) Ограничения текущего MVP

- Stage5 сейчас пишет итоговый файл как технический артефакт-агрегат; при переходе к production заменить на реальную склейку аудио.
- TTS в Stage4 сейчас mock-синтезатор (для стабильной отладки контракта и интеграции).

