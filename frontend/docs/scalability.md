# Scalability roadmap

## Горизонтальное масштабирование

### Web (Next.js)

- Деплой как SSR/edge или static + API base URL.\n+- CDN/edge caching для лендинга.\n+- Кэширование списков голосов (stale-while-revalidate).

### API (NestJS)

- Stateless инстансы за load balancer.\n+- Перенос in-memory rate limiting на Redis.\n+- Добавление централизованного логирования и трассировки.

### Workers (BullMQ)

- Масштабирование воркеров независимо от API.\n+- Приоритеты очередей (короткие задачи выше).\n+- Retrying и DLQ (dead letter) для ошибок провайдера TTS.

## Разделение сервисов (когда станет тесно)

- **tts-service**:\n+  - отдельный сервис, который инкапсулирует провайдера/модель;\n+  - принимает задания (HTTP/gRPC) и возвращает результат в storage;\n+  - даёт единый интерфейс для разных провайдеров.\n+- **billing-service**:\n+  - интеграция со Stripe/ЮKassa;\n+  - вебхуки, синхронизация статуса подписки;\n+  - выдача квот и прав (`canDownload`, `maxCharactersMonth`).\n+
## Данные и хранение\n+
- PostgreSQL:\n+  - индексы по `userId`, `projectId`, `createdAt` уже заложены;\n+  - при росте — партиционирование таблиц usage/логов.\n+- Storage:\n+  - включить lifecycle policies (удаление старых preview/версий);\n+  - подпись URL (если когда-то понадобится download) — только после проверки прав.\n+
## Наблюдаемость\n+
- Метрики:\n+  - latency API, error rate,\n+  - длительность генерации,\n+  - очередь: depth, time-in-queue.\n+- Алёрты на рост ошибок провайдера и таймаутов.\n+
## UX на статусах\n+
- Сейчас: polling списков аудио.\n+- Далее: SSE/WebSocket канал для пуш-статусов по `Audio`.\n+
