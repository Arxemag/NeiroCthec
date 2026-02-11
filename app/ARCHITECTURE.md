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


## 2.1) Детальный поток данных между стадиями (что откуда и куда)

Ниже — практический контракт, который важен для frontend/mobile и backend интеграции.

### Stage0 (source -> Line rows)

**Вход:**
- `Book.source_path` (файл, загруженный через `POST /books/upload`).

**Действия:**
- читает файл построчно;
- создаёт записи `Line` в БД;
- выставляет первичные поля: `idx`, `original`, `type`, `speaker`, `segments`;
- переводит книгу в `parsing`.

**Выход в БД:**
- новые `Line` со статусом `tts_status = new`.

**Что появляется после Stage0:**
- книга уже существует в БД;
- у книги есть набор строк `Line`, но TTS задач ещё нет.

---

### Stage1 (new -> stage1_done)

**Вход:**
- `Line` со статусом `new`.

**Действия:**
- структурный проход;
- подтверждает, что строка прошла Stage1.

**Выход в БД:**
- `Line.tts_status = stage1_done`.

**Что появляется после Stage1:**
- строки готовы к Stage2 (speaker/type/segments нормализация).

---

### Stage2 (stage1_done -> stage2_done)

**Вход:**
- `Line` со статусом `stage1_done`.

**Действия:**
- нормализует `type`;
- определяет/уточняет `speaker`;
- нормализует `segments` (если пусто, формирует базовый сегмент);
- переводит строку в следующий статус.

**Выход в БД:**
- `Line.type`, `Line.speaker`, `Line.segments` гарантированно заполнены;
- `Line.tts_status = stage2_done`.

**Что появляется после Stage2:**
- строка становится валидной для эмоций и TTS-контракта.

---

### Stage3 (stage2_done -> tts_pending + TTSTask)

**Вход:**
- `Line` со статусом `stage2_done`.

**Действия:**
- рассчитывает/проставляет `emotion`;
- ставит строку в `tts_pending`;
- создаёт `TTSTask` (если ещё не создан) с payload для Stage4.

**Payload, который уходит в TTS queue (`TTSTask.payload`):**
- `line_id`
- `user_id`
- `book_id`
- `text` (из `Line.original`)
- `emotion`
- `voice` (из `Line.speaker`)

**Выход в БД:**
- `Line.emotion` заполнен;
- `Line.tts_status = tts_pending`;
- `TTSTask.status = pending`.

**Что появляется после Stage3:**
- задача доступна для Stage4 через `/internal/tts-next`.

---

### Stage4 (отдельный контейнер, pull-модель)

**Откуда получает:**
- Stage4 вызывает `POST /internal/tts-next` в Core API.

**Что получает:**
- одну pending-задачу (`task_id`, `line_id`, `user_id`, `book_id`, `text`, `voice`, `emotion`).

**Действия:**
- синтезирует WAV (`/tts` локальная логика worker);
- кладёт WAV в object storage;
- отправляет callback в Core: `POST /internal/tts-complete` с `line_id` и `audio_path`.

**Что меняется в Core после callback:**
- `Line.audio_path` заполняется;
- `Line.tts_status = tts_done`;
- `TTSTask.status = done`.

---

### Stage5 (когда все строки книги = tts_done)

**Условие запуска:**
- для книги нет строк вне `tts_done`.

**Действия:**
- сортирует строки по `idx`;
- собирает финальный артефакт книги;
- сохраняет путь в `Book.final_audio_path`.

**Выход в БД:**
- `Line.tts_status = assembled`;
- `Book.status = completed`.

**Что получает клиент:**
- `GET /books/{id}/download` становится доступен.



## 2.2) Реальная NLP-цепочка по модулям (как сейчас в коде `core/pipeline`)

Ниже — именно та декомпозиция, которая важна для quality frontend/mobile (экраны глав, статусы обработки, debug-панели).

### Stage0 — формат книги

Подэтапы:
- **0.1 `FormatDetector`**: определяет тип входа (`txt`/`fb2`) по расширению.
- **0.2 `FormatParser`**: читает файл в raw text.

Результат Stage0:
- нормализованный текст книги (`raw_text`, `lines`, `source_format`) для последующих этапов.

---

### Stage1 — структура книги и подготовка текста под озвучку

Подэтапы:

1. **1.1 `ChapterParser`**
   - разбивка на главы по паттернам вида `Глава N` / `Chapter N`;
   - формируется список `Chapter(index, title, lines)`.

2. **1.2 `LineTypeParser`**
   - из глав строятся `Line`;
   - присваивается тип: `dialogue` или `narrator`.

3. **1.3 `SegmentAnalyzer`**
   - разбивает строку на сегменты;
   - в диалогах учитывает ремарки (кто сказал/как сказал) и сохраняет их в структуре.

4. **1.4 `SegmentTextAdapter`**
   - адаптирует текст сегмента под TTS;
   - добавляет финальное многоточие `…` там, где нужно для естественной интонации.

5. **1.5 `Stress`**
   - расставляет ударения/стресс-марки для TTS-текста.

Результат Stage1 (важно для клиента):
- книга разбита **по главам**;
- каждая глава содержит строки narrator/dialogue;
- строки разбиты на сегменты с tts-ready текстом.

> То есть на выходе пайплайна логически должен быть и аудио-выход **по главам** (не только единый файл книги).

---

### Stage2 — определение говорящего (speaker resolution)

Это единый контрактный этап с внутренними модулями:

1. **2.0 `verb_dictionary`**
   - словарь глаголов/форм прошедшего времени (male/female признаки).

2. **2.1 `evidence_collectors`**
   - сбор признаков (местоимения, имена, грамматические маркеры и т.д.).

3. **2.2 `evidence_resolver`**
   - агрегирует признаки и считает итоговые веса уверенности.

4. **2.3 `context_manager`**
   - учитывает контекст диалога (последовательность реплик, чередование).

5. **2.4 `fallback_strategies`**
   - fallback-логика, если уверенность низкая.

6. **2.x `stage2_speaker_resolver`**
   - фасад-оркестратор Stage2: объединяет 2.0–2.4 и делает финальный mapping персонажей и назначение `speaker` через весовую модель.

Результат Stage2:
- для каждой строки/сегмента появляется валидный `speaker` и обоснованное решение по говорящему.


### Статус интеграции Stage2 (важно)

В текущей версии `stage2_speaker_resolver` выступает как **оркестратор**:
- использует 2.0 (динамический словарь глаголов/контекста);
- использует 2.1 + 2.2 (collect evidences + resolve confidence);
- использует 2.3 (контекст диалога/сегментов);
- использует 2.4 (fallback strategy);
- при ошибках в подмодулях безопасно откатывается на внутреннюю аналитику, чтобы не ломать Stage2.

---

### Stage3 — эмоции и параметры подачи

Подэтапы:
- **`SpeechDirector`** — просодия/темп/паузы/громкость по ремаркам и пунктуации.
- **`TTSDirector`** — lightweight метаданные для TTS (volume/tempo/emotion/emphasis/pause).

Результат Stage3:
- у каждого сегмента/строки появляются emotion/tts-meta,
- данные готовы для передачи в Stage4 TTS.


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

