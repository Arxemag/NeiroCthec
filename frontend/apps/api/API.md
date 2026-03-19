## Neurochtec API (MVP)

Base URL: `http://localhost:4000`

### Auth

#### `POST /api/auth/register`

Body:
- `email` string
- `password` string (min 8)

Response:
- `user` { id, email, role, subscriptionStatus }
- `accessToken` string (Bearer)
- `refreshToken` string (also set as httpOnly cookie `refreshToken`)

#### `POST /api/auth/login`

Body: same as register.
Response: same as register.

#### `GET /api/auth/me`

Auth: `Authorization: Bearer <accessToken>`
Response: `{ user: JwtAccessPayload }`

#### `POST /api/auth/refresh`

Auth: refresh token via cookie `refreshToken` (or Bearer refresh token).
Response: same as login/register (rotates refresh).

#### `POST /api/auth/logout`

Auth: refresh token via cookie.
Response: `{ ok: true }`

### Users

#### `GET /api/users/me`

Auth: Bearer access token.
Response: `{ user: { id, email, role, subscriptionStatus, createdAt } }`

#### `GET /api/users/me/voices`

Auth: Bearer access token.
Response: `{ voices: { id, name, coreVoiceId, projectId?, createdAt }[] }` — метаданные своих голосов (файлы в Core).

#### `POST /api/users/me/voices`

Auth: Bearer access token.
Body: `{ name: string, coreVoiceId: string, projectId?: string }`. Регистрация своего голоса по `coreVoiceId` (после загрузки WAV в Core).
Response: `{ voice: { id, name, coreVoiceId, projectId?, createdAt } }`.

#### `PATCH /api/users/me/voices/:id`

Auth: Bearer access token.
Body: `{ name?: string, projectId?: string | null }`.
Response: `{ voice: ... }`.

#### `DELETE /api/users/me/voices/:id`

Auth: Bearer access token.
Response: `{ ok: true }`.

#### `GET /api/users/me/custom-voices`

Auth: Bearer access token.
Behavior: прокси к Core `GET /voices` с заголовком `X-User-Id` (источник правды — Core: встроенные + свои по user_id). Если не заданы `CORE_API_URL`/`APP_API_URL`: `501 Not Implemented`.
Response: `{ voices: CoreVoice[] }` (формат как у Core: id, name, role?, sample_url?).

### Voices

#### `GET /api/voices?language=ru-RU&gender=female&style=neutral`

Auth: Bearer access token.
Response: `{ voices: VoiceSummary[] }`

#### `GET /api/voices/:id`

Auth: Bearer access token.
Response: `{ voice: VoiceSummary }`

#### `GET /api/voices/:id/sample`

Auth: Bearer access token.
Response: audio stream (404 if no sample).

### Projects

#### `GET /api/projects`

Auth: Bearer access token.
Response: `{ projects: { id, title, language, status, createdAt, updatedAt }[] }`

#### `POST /api/projects`

Auth: Bearer access token.
Body:
- `title` string
- `text` string
- `language` string (e.g. `ru-RU`)
- `voiceIds` string[]

Response: `{ project: Project }`

#### `GET /api/projects/:id`

Auth: Bearer access token.
Response: `{ project: Project + voices[], voiceSettings? }`. Поле `voiceSettings`: `{ narratorVoiceId?, maleVoiceId?, femaleVoiceId? }` — последний сохранённый выбор голосов по ролям для подстановки при озвучке.

#### `GET /api/projects/:id/voices`

Auth: Bearer access token.
Response: `{ voices: { id, name, coreVoiceId, projectId?, createdAt }[] }` — голоса пользователя + привязанные к этому проекту (для UI «Мои голоса»).

#### `GET /api/projects/:id/available-voices`

Auth: Bearer access token.
Behavior: прокси к Core `GET /voices` с заголовком `X-User-Id`. Если не заданы `CORE_API_URL`/`APP_API_URL`: `501 Not Implemented`.
Response: `{ voices: CoreVoice[] }`.

#### `PATCH /api/projects/:id`

Auth: Bearer access token.
Body: any of `title`, `text`, `language`, `voiceIds`, `speakerSettings`, `voiceSettings`.
- `speakerSettings` — опциональный объект по спикерам: `{ narrator?: { tempo?, pitch? }, male?, female? }`. Темп 0.5–2, pitch −1…1.
- `voiceSettings` — сохранённый выбор голосов по ролям: `{ narratorVoiceId?, maleVoiceId?, femaleVoiceId? }` (строки — coreVoiceId или id голоса).
Response: `{ project: Project }`

### Audio

#### `POST /api/projects/:id/preview-by-speakers` (опционально)

Auth: Bearer access token.
Body (optional): `{ bookId?: string }`.
Behavior: если настроены `CORE_API_URL` или `APP_API_URL`, запрос проксируется в Core `POST .../internal/preview-by-speakers` с телом `{ projectId, bookId }`. Ответ Core — три сэмпла (narrator, male, female): либо объект с полями `narrator`, `male`, `female` (URL или base64), либо `{ urls: { narrator?, male?, female? } }`. Контракт согласовать с Frontend и Core.
Если Core URL не задан: `501 Not Implemented` (превью может отдаваться напрямую с Core).
Response: см. контракт Core.

#### `POST /api/projects/:id/generate-audio`

Auth: Bearer access token.
Behavior:
- создаёт `Audio(status=queued)`
- ставит задачу в очередь BullMQ `generate-audio`

Response: `{ audio: Audio }`

#### `GET /api/projects/:id/audios`

Auth: Bearer access token.
Response: `{ audios: { id, status, format, durationSeconds, createdAt }[] }`

#### `POST /api/projects/:id/complete`

Auth: Bearer access token.
Body: none (project `id` in path).
Behavior: помечает проект как завершённый (`status = ready`). Доступ только у владельца проекта.
Response: `{ project: Project }` (проект с обновлённым status).
Errors: `404` — проект не найден или в корзине; `403` — не владелец.

#### `GET /api/projects/:id/chapters`

Auth: Bearer access token.
Response: `{ chapters: Chapter[] }`, где каждая глава: `{ id, title, audioId?, durationSeconds?, createdAt }`. Порядок по дате создания аудио. Источник — записи Audio по проекту (одна «глава» на один аудиофайл).
Errors: `404` — проект не найден или в корзине; `403` — не владелец.

#### `POST /api/projects/:id/upload-text`

Auth: Bearer access token.
Body: `multipart/form-data`, поле `file` — текстовый файл (например .txt). Лимит размера: 1 MB.
Behavior: содержимое файла записывается в поле `text` проекта. Доступ только у владельца.
Response: `{ ok: true }`.
Errors: `400` — файл не передан, пустой или не текст; `404` — проект не найден или в корзине; `403` — не владелец.

#### `GET /api/audios/:id/stream`

Auth: Bearer access token.
Response: audio stream from S3 via backend proxy.
Supports `Range: bytes=start-end`.

### Контракт с Core (TTS)

При полной озвучке книги (вызов Core из воркера или из Nest при проксировании) в теле запроса к Core передаётся объект настроек спикеров, чтобы Core применял темп и тембр по ролям (narrator, male, female). Backend (Nest) не парсит содержимое TTS; при проксировании просто пробрасывает body как есть.

- **Тело запроса к Core (озвучка книги)** должно включать (по согласованию с Frontend/TTS):
  - `speakerSettings?: { narrator?: { tempo?: number, pitch?: number }, male?: { tempo?, pitch? }, female?: { tempo?, pitch? } }`
  - Темп (tempo): множитель скорости, типично 0.5–2.
  - Тембр (pitch): сдвиг в полутонах, типично −1…1.
- Настройки по умолчанию хранятся в проекте Nest (`GET/PATCH /api/projects/:id`) и при «Отправить книгу на озвучку» передаются в Core в теле запроса.

### Subscription (stub)

#### `GET /api/subscription`

Auth: Bearer access token.
Response: `{ subscription: { status, plan? } }`

#### `POST /api/subscription/upgrade`

Auth: Bearer access token.
Behavior: stub upgrade — sets `subscriptionStatus=active` and attaches `Pro` plan if exists.
Response: `{ subscription: ... }`

