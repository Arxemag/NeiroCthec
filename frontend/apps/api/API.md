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
Response: `{ project: Project + voices[] }`

#### `PATCH /api/projects/:id`

Auth: Bearer access token.
Body: any of `title`, `text`, `language`, `voiceIds`.
Response: `{ project: Project }`

### Audio

#### `POST /api/projects/:id/generate-audio`

Auth: Bearer access token.
Behavior:
- создаёт `Audio(status=queued)`
- ставит задачу в очередь BullMQ `generate-audio`

Response: `{ audio: Audio }`

#### `GET /api/projects/:id/audios`

Auth: Bearer access token.
Response: `{ audios: { id, status, format, durationSeconds, createdAt }[] }`

#### `GET /api/audios/:id/stream`

Auth: Bearer access token.
Response: audio stream from S3 via backend proxy.\n+Supports `Range: bytes=start-end`.

### Subscription (stub)

#### `GET /api/subscription`

Auth: Bearer access token.
Response: `{ subscription: { status, plan? } }`

#### `POST /api/subscription/upgrade`

Auth: Bearer access token.
Behavior: stub upgrade — sets `subscriptionStatus=active` and attaches `Pro` plan if exists.
Response: `{ subscription: ... }`

