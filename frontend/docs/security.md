# Security & limits (MVP)

## Auth

- Пароли: `argon2` хеширование (см. `apps/api/src/modules/auth/auth.service.ts`).\n+- Access token: короткий TTL, передача через `Authorization: Bearer ...`.\n+- Refresh token: httpOnly cookie + rotation.\n+
## Input validation

- Глобальная `ValidationPipe` (whitelist + forbidNonWhitelisted).\n+- DTO-валидация для auth и проектов.\n+
## Access control

- Любые `/api/*` кроме `/api/health` требуют auth по месту (guards).\n+- Объекты `Project`/`Audio` доступны только владельцу (`userId`).\n+
## Rate limiting (простая защита от злоупотреблений)

- Middleware `simpleRateLimit` на:\n+  - `/api/auth` (30 req/min per IP)\n+  - `/api/projects` (120 req/min per IP)\n+\n+Для production рекомендовано заменить на Redis-based rate limiter (чтобы лимиты были общими для всех инстансов API).

## Product limits (MVP)

- Ограничения free-плана управляются env-переменными:\n+  - `FREE_MAX_CHARS_PER_REQUEST`\n+  - `FREE_MAX_REQUESTS_PER_DAY`\n+\n+Проверка выполняется при `POST /api/projects/:id/generate-audio` (см. `apps/api/src/modules/audios/audios.service.ts`).\n+
## Media security

- Аудио хранится в S3/MinIO и **не выдаётся публично**.\n+- Стриминг идёт через `/api/audios/:id/stream` с проверкой владельца.\n+
