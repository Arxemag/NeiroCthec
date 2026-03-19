# StorageConventionsModule (S3/MinIO) — Техническое задание

## Назначение и ответственность

- **Что делает модуль**:
  - Определяет единые соглашения по хранению бинарных артефактов в S3/MinIO.
  - Определяет правила доступа/изоляции по `clientId`.
  - Описывает naming keys, retention/TTL, и совместимость между модулями.
- **Что модуль НЕ делает**:
  - Не выполняет бизнес-логику; только правила/контракты.

## Target: базовые принципы

- **Единый MinIO(S3)**, но логическое владение через prefix:
  - каждый модуль пишет **только** в свои prefix-и.
- **SoT в Postgres**:
  - S3 хранит blobs, Postgres хранит `bucket/key/contentType/size/duration/hash`.
- **Артефакт адресуется по (clientId, taskId)**.

## Bucket/prefix layout (предложение)

Один bucket `neurochtec` (или несколько, если нужен раздел по политикам).

Prefix:
- `core/books/<clientId>/<bookId>/source/<sourceId>.txt`
- `core/tasks/<clientId>/<taskId>/input.json`
- `core/tasks/<clientId>/<taskId>/output.wav` (если Core владеет output; иначе stage4)
- `stage4/tasks/<clientId>/<taskId>/output.wav`
- `stage5/assemblies/<clientId>/<assemblyId>/final.wav`
- `voices/<clientId>/<voiceId>.wav` (если голоса тоже в S3)
- `previews/<clientId>/<previewId>.wav`

## Key naming и идемпотентность

- `taskId` детерминированный ⇒ `key` может быть детерминированным:
  - `stage4/tasks/<clientId>/<taskId>.wav`
- Запись должна быть safe:
  - либо overwrite разрешён,
  - либо используется conditional put + версия (ETag), а в DB фиксируется фактическая версия.

## Retention/TTL

Target:
- previews: TTL 7–30 дней
- промежуточные артефакты (parts/chunks): TTL (опционально) после сборки final
- финалы/главы: без TTL или по бизнес-правилам подписки

## Доступ и безопасность

Варианты:
- **Backend-only streaming** (as-is в Nest аудио стримится через backend).
- **Signed URLs** на чтение с коротким TTL (если UI должен качать напрямую).

Выбор фиксируется в Website/Core API контрактах.

## Критерии приёмки

- [x] Любой артефакт имеет запись в Postgres (bucket/key/hash/owner).
- [x] Нельзя прочитать артефакт чужого `clientId`.

