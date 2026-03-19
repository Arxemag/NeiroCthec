# ТЗ по модулям (NeiroCthec)

Эта папка содержит **ТЗ по каждому модулю** системы. Принцип: модули общаются **только по публичным контрактам** (HTTP/API, очереди, хранилища), без прямых импортов и скрытых зависимостей.

## Как читать

- Начните с `SYSTEM_OVERVIEW.md` — там общий контур и основные сценарии.
- Затем откройте ТЗ модулей по цепочке данных: Website → Core → Queue/Stage4 → TTS → Storage.

## Список модулей

- `SYSTEM_OVERVIEW.md`
- `WEBSITE_MODULE.md` (Next.js + NestJS как единый модуль)
- `INFRA_MODULE.md` (Postgres/Redis/MinIO + docker-compose)
- `CORE_API_MODULE.md` (FastAPI Core)
- `PIPELINE_STAGE1_MODULE.md`
- `PIPELINE_STAGE2_MODULE.md`
- `PIPELINE_STAGE3_MODULE.md`
- `PIPELINE_STAGE4_WORKER_MODULE.md`
- `PIPELINE_STAGE5_ASSEMBLER_MODULE.md`
- `TTS_QWEN3_ENGINE_MODULE.md`
- `TTS_XTTS2_ENGINE_MODULE.md`
- `STORAGE_CONVENTIONS_MODULE.md`

## Шаблон

Для новых модулей используйте `_TEMPLATE_MODULE_SPEC.md`.

