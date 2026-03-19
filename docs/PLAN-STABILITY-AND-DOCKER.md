# План глобальной переделки: стабильность и Docker

Цель: убрать повторяющиеся ошибки по коннекту между контейнерами, инициализации (Prisma, типы, TTS) и сделать один предсказуемый способ запуска.

---

## 1. Docker: порядок запуска и здоровье сервисов

### 1.1 Проблемы сейчас

- **Connection refused** — сервис A стартует раньше, чем B начал слушать порт.
- **Read timed out** — таймауты к TTS меньше, чем реальное время ответа.
- **Prisma / class-validator** — api/worker зависят от тома `frontend_node_modules`, в котором может не быть сгенерированного клиента или «правильных» типов.

### 1.2 Что сделать

| Область | Действие |
|--------|----------|
| **Инфраструктура** | Добавить **healthcheck** для postgres, redis, minio (curl/pg_isready/redis-cli ping). |
| **Core** | Healthcheck: `GET http://localhost:8000/health` (или аналог). `depends_on` у stage4 и web — `core: service_healthy`. |
| **tts-xtts** | Оставить healthcheck на `/health`, при необходимости увеличить `start_period` (например до 300 с). |
| **stage4** | Уже ждёт `tts-xtts: service_healthy`. Добавить **restart: on-failure** (и при необходимости ограничение retries). |
| **frontend_deps** | Гарантировать один успешный прогон перед api/web: оставить `condition: service_completed_successfully`. При первом `up` дождаться завершения frontend_deps. |
| **api / worker** | В команде запуска **всегда** первым шагом вызывать `prisma generate` (уже есть). Не полагаться только на frontend_deps. |

Итог: у каждого сервиса, от которого зависят другие, есть healthcheck; зависимые сервисы стартуют по `service_healthy` / `service_completed_successfully`.

---

## 2. Frontend (Nest API): инициализация без сюрпризов

### 2.1 Проблемы сейчас

- **Cannot find module '.prisma/client/default'** — в томе нет сгенерированного клиента.
- **Module 'class-validator' has no exported member 'IsOptional' / 'Min' / …** — типы пакета в окружении (Docker/workspace) не совпадают с ожидаемыми.
- **Could not find a declaration file for '@nestjs/platform-express'** — типы не подтягиваются.

### 2.2 Что сделать

| Область | Действие |
|--------|----------|
| **Prisma** | В **каждом** процессе, который использует Prisma (api, worker), в самом начале команды запуска вызывать `prisma generate`. Не удалять этот шаг из `command` в docker-compose. |
| **class-validator** | Ввести **единственную точку входа**: модуль-шим `src/lib/validators.ts`, который делает `require('class-validator')` и реэкспортирует нужные декораторы. Во всех DTO заменить импорты с `'class-validator'` на этот модуль. Типы тогда не зависят от того, как пакет экспортирует типы в текущем окружении. |
| **@nestjs/platform-express** | Аналогично: шим `src/lib/nestjs-platform-express.ts` с `require('@nestjs/platform-express')` и реэкспортом `FileInterceptor`. В контроллерах импортировать из шима. |
| **Версии** | В `frontend/apps/api/package.json` зафиксировать версии критичных пакетов (class-validator, @nestjs/*, prisma) без `^` там, где уже были сбои (например `class-validator: "0.13.2"`). |

Итог: Prisma всегда генерируется при старте api/worker; типы и импорты не зависят от «капризного» разрешения типов в node_modules.

---

## 3. TTS и Stage4

### 3.1 Проблемы сейчас

- **Connection refused** к tts-xtts — stage4 стартует раньше, чем tts-xtts поднял порт (или контейнер падает).
- **Read timed out** — один запрос к XTTS занимает больше 300 с (первый запрос или тяжёлый чанк).

### 3.2 Что сделать

| Область | Действие |
|--------|----------|
| **tts-xtts** | Healthcheck по `GET /health` с достаточным `start_period` (например 120–300 с). В логах оставить пошаговый вывод (резолв speaker, чанки, время). |
| **stage4** | Зависимость `tts-xtts: service_healthy` уже есть. Таймауты для XTTS вынести в переменные (например `EXTERNAL_TTS_XTTS_TIMEOUT_SEC=600`) и не уменьшать без необходимости. |
| **Повтор при сбое** | Опционально: в stage4 при `Connection refused` или `Read timed out` делать ограниченное число повторов с паузой (например 2–3 раза с интервалом 30 с), затем помечать задачу как failed. Это уменьшит «разовые» падения из-за медленного старта TTS. |

Итог: TTS считается готовым только после healthcheck; таймауты достаточные; при желании — мягкие повторы при временных сбоях.

---

## 4. Один способ запуска и документация

### 4.1 Что сделать

| Область | Действие |
|--------|----------|
| **README в корне** | Добавить раздел «Запуск в Docker»: 1) первый раз — `docker compose up -d frontend_deps`, дождаться выхода; 2) затем `docker compose up -d`; 3) при изменении schema.prisma — `docker compose run --rm api sh -c "npm run -w apps/api prisma:generate"` и перезапуск api/worker. |
| **Скрипт запуска** | Один скрипт (например `scripts/docker-up.sh` или цель в Makefile): проверка наличия .env, при необходимости запуск frontend_deps, затем `docker compose up -d` с списком сервисов. Так все всегда будут использовать один и тот же порядок. |
| **Переменные окружения** | В README или в `docs/ENV.md` — таблица переменных (DATABASE_URL, APP_API_URL, EXTERNAL_TTS_*, NEXT_PUBLIC_*, и т.д.) с кратким описанием. Это уменьшит ошибки из-за неправильного конфига. |

Итог: один документированный способ поднять стек и обновить схему/зависимости.

---

## 5. Проверка здоровья и отладка

### 5.1 Что сделать

| Область | Действие |
|--------|----------|
| **Проверка после up** | В README или в скрипте: последовательно проверить `docker compose ps` (все в состоянии running/healthy), затем curl на api (4000), web (3000), core (8000). При наличии — простая страница «статус» в приложении (доступность api, core, при желании TTS). |
| **Логи** | В документации явно указать: при ошибках смотреть логи api, core, stage4, tts-xtts (`docker compose logs -f <service>`). Для tts-xtts включить небуферизованный вывод (PYTHONUNBUFFERED=1). |
| **Типичные ошибки** | В `docs/TROUBLESHOOTING.md` кратко описать: Connection refused → проверить healthcheck и порядок запуска; Prisma/client not found → выполнить prisma generate в контейнере api; таймауты TTS → увеличить EXTERNAL_TTS_XTTS_TIMEOUT_SEC и проверить логи tts-xtts. |

Итог: после деплоя можно быстро убедиться, что всё живое, и по шагам разобрать типичные сбои.

---

## 6. Порядок внедрения (приоритеты)

1. **Сначала (минимум для стабильности)**  
   - Healthchecks для postgres, redis, minio, core, tts-xtts.  
   - depends_on с `service_healthy` для api/web от core, для stage4 от tts-xtts (уже частично есть).  
   - В api/worker в команде запуска всегда первым шагом `prisma generate`.  
   - Шимы для class-validator и @nestjs/platform-express в Nest API и замена импортов.

2. **Затем**  
   - README с разделом «Запуск в Docker» и разделом про обновление Prisma.  
   - Один скрипт запуска (например `scripts/docker-up.sh`).  
   - Таблица переменных окружения в README или ENV.md.

3. **По желанию**  
   - Повторы запросов в stage4 при Connection refused / timeout.  
   - Страница «статус» в приложении.  
   - TROUBLESHOOTING.md с типичными ошибками и решениями.

После выполнения пунктов раздела 1 и 2 ошибки по коннекту между контейнерами и по инициализации (Prisma, типы) должны уйти или воспроизводиться предсказуемо, а их устранение — быть описанным в документации.
