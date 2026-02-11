# Auth flow (MVP)

## Цели

- Простая авторизация **email + пароль**.
- Быстрый UX для web (авто-обновление access token).
- Возможность отзыва refresh token (logout/rotation).

## Механика

- **Access token**: JWT (короткий TTL), передаётся в `Authorization: Bearer ...`.
- **Refresh token**: JWT (длинный TTL), хранится в:
  - httpOnly cookie `refreshToken` (primary для web), и
  - также возвращается в JSON (удобно для тестов/интеграций).

Backend хранит **refresh token** в таблице `RefreshToken` (в виде хеша), с флагом `revokedAt` и `expiresAt`.

## Последовательности

### Регистрация / логин

1) `POST /api/auth/register` или `POST /api/auth/login`.\n+2) Backend выдаёт `accessToken` и `refreshToken`, и ставит cookie `refreshToken`.\n+3) Frontend сохраняет `accessToken` в `localStorage`.\n+
### Авто-обновление access token

1) Любой API-запрос с `Authorization`.\n+2) Если backend отвечает `401`, frontend делает `POST /api/auth/refresh` (с `credentials: include`).\n+3) Если refresh успешен — backend **ротирует** refresh token, выдаёт новый `accessToken`, обновляет cookie.\n+4) Frontend повторяет исходный запрос.

### Logout

1) `POST /api/auth/logout` (refresh token берётся из cookie).\n+2) Backend помечает refresh token как `revokedAt`.\n+3) Backend очищает cookie `refreshToken`.\n+4) Frontend очищает `localStorage` access token.

## Замечания по безопасности (MVP)

- Cookie `refreshToken`: `httpOnly`, `sameSite=lax`, `secure` в production.\n+- Access token хранится в `localStorage` (MVP-компромисс). Для повышения защиты от XSS можно перейти на хранение access token только в памяти + обновление по cookie.

