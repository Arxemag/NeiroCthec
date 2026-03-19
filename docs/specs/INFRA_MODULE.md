# InfraModule (Postgres + Redis + MinIO) — Техническое задание

## Назначение и ответственность

- **Что делает модуль**:
  - Поднимает инфраструктурные сервисы окружения: Postgres (SoT), Redis (очереди/кэш), MinIO (S3 для артефактов).
  - Гарантирует предсказуемый порядок старта и healthchecks.
- **Что модуль НЕ делает**:
  - Не содержит бизнес-логики.

## Границы и зависимости

- **Код/конфиг**: `docker-compose.yml` (корень), а также `frontend/docker-compose.yml`, `app/docker-compose.yml` (если используются).
- **Зависимые модули**: WebsiteModule, CoreApiModule, Stage4WorkerModule.

## Публичные контракты

### Postgres

- **Назначение**: источник правды для доменных сущностей и статусов пайплайна (target).
- **Доступ**: через `DATABASE_URL`.

### Redis

- **Назначение**:
  - WebsiteModule (Nest): BullMQ (as-is).
  - Target: общая очередь задач TTS (Core↔Stage4), plus DLQ/metrics.
- **Доступ**: `REDIS_URL`.

### MinIO (S3)

- **Назначение**: хранение бинарных артефактов (WAV, промежуточные результаты, previews).
- **Доступ**: `S3_ENDPOINT` + credentials.

## Конфигурация (as-is)

См. `docker-compose.yml` и `docs/ENV.md`.

## Нефункциональные требования (target)

- **Доступность**:
  - Postgres/Redis/MinIO должны иметь healthcheck и использоваться в `depends_on`.
- **Безопасность**:
  - MinIO без публичных URL; доступ к объектам только через backend proxy/подписанные URL (policy выбирается в StorageConventions).
- **Резервное копирование**:
  - Postgres backup + MinIO bucket backup/replication.

## Критерии приёмки

- [x] `docker compose up -d` поднимает инфраструктуру в состоянии healthy.
- [x] Зависимые сервисы стартуют только после ready (healthcheck).

