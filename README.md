# НейроЧтец — SaaS-платформа ИИ-озвучки (MVP scaffold)

Монорепозиторий с:
- `apps/web`: Next.js (TypeScript) — лендинг и личный кабинет
- `apps/api`: NestJS (TypeScript) — REST API, auth, проекты, голоса, аудио
- `packages/shared`: общие типы/DTO (минимально для MVP)

## Быстрый старт (локально)

### 1) Инфраструктура

Поднять сервисы (Postgres, Redis, MinIO):

```bash
docker compose up -d
```

### 2) API

В отдельном терминале:

```bash
cd apps/api
npm install
npm run prisma:generate
npm run prisma:migrate
npm run seed
npm run dev
```

### 3) WEB

В отдельном терминале:

```bash
cd apps/web
npm install
npm run dev
```

## Важное про аудио

- В MVP аудио хранится **в S3-совместимом хранилище (MinIO)**, но доступ наружу не выдаётся.\n+- Воспроизведение идёт через защищённый endpoint `/api/audios/:id/stream`.\n+- Скачивание (download) не реализовано; для неактивной подписки ограничение жёстко проверяется на backend.

## Переменные окружения

См. `.env.example` в корне и `apps/api/.env.example`, `apps/web/.env.example`.

