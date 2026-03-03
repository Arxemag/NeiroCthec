## ТЗ: Синхронизация голосов из файловой системы

**Метод:** POST  
**Путь:** `/api/voices/sync-from-filesystem`  
**Описание:** Синхронизирует голоса из файловой системы (`public/cache/voices/audio/`) в базу данных. Сканирует папку с аудио файлами и создает/обновляет записи в базе данных на основе имен файлов и метаданных.

---

### Request

#### Headers
```
Authorization: Bearer <token>  # требуется авторизация
Content-Type: application/json
```

#### Request Body
```json
{
  "basePath": "/cache/voices",
  "force": false
}
```

**Схема валидации:**
- `basePath`: string, необязательное, по умолчанию `/cache/voices` - базовый путь к папке с голосами
- `force`: boolean, необязательное, по умолчанию `false` - если true, обновляет существующие голоса

---

### Response

#### Success Response (200)
```json
{
  "success": true,
  "synced": 5,
  "created": 3,
  "updated": 2,
  "errors": [],
  "voices": [
    {
      "id": "voice-id",
      "name": "Диктор 1",
      "role": "narrator",
      "gender": "neutral",
      "language": "ru",
      "audioFile": "/cache/voices/audio/narrator_1.mp3"
    }
  ]
}
```

#### Error Responses

**400 Bad Request**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid base path"
  }
}
```

**401 Unauthorized**
```json
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required"
  }
}
```

**500 Internal Server Error**
```json
{
  "success": false,
  "error": {
    "code": "SYNC_ERROR",
    "message": "Failed to sync voices",
    "details": ["Error reading directory", "Error parsing metadata"]
  }
}
```

---

### Логика работы

1. **Сканирование файлов:**
   - Читает папку `public/cache/voices/audio/` (или путь из `basePath`)
   - Находит все аудио файлы (`.mp3`, `.wav`, `.ogg`)
   - Парсит имена файлов по формату: `{role}_{index}.{ext}`

2. **Парсинг имен файлов:**
   - Формат: `{role}_{index}.{ext}`
   - Роли: `narrator` (Диктор), `male` (Мужской голос), `female` (Женский голос)
   - Примеры:
     - `narrator_1.mp3` → роль: narrator, индекс: 1
     - `male_2.wav` → роль: male, индекс: 2
     - `female_1.ogg` → роль: female, индекс: 1

3. **Загрузка метаданных:**
   - Читает файл `public/cache/voices/meta/voice-metadata.json`
   - Ищет метаданные для каждого голоса по имени файла или ID
   - Если метаданных нет, создает базовые на основе имени файла

4. **Создание/обновление записей:**
   - Для каждого файла создает или обновляет запись в таблице `Voice`
   - Использует `providerVoiceId` = `{role}_{index}` для уникальности
   - Если `force = false` и голос уже существует, пропускает обновление

5. **Маппинг ролей:**
   - `narrator` → `role = "narrator"`, `gender = "neutral"`
   - `male` → `role = "actor"`, `gender = "male"`
   - `female` → `role = "actor"`, `gender = "female"`

---

### Примеры использования

#### Пример запроса
```bash
curl -X POST https://api.example.com/api/voices/sync-from-filesystem \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "basePath": "/cache/voices",
    "force": false
  }'
```

#### Пример успешного ответа
```json
{
  "success": true,
  "synced": 5,
  "created": 3,
  "updated": 2,
  "errors": [],
  "voices": [
    {
      "id": "clx123...",
      "name": "Диктор 1",
      "role": "narrator",
      "gender": "neutral",
      "language": "ru",
      "style": "default",
      "provider": "local",
      "providerVoiceId": "narrator_1",
      "sampleStorageKey": null,
      "isActive": true
    },
    {
      "id": "clx456...",
      "name": "Мужской голос 1",
      "role": "actor",
      "gender": "male",
      "language": "ru",
      "style": "default",
      "provider": "local",
      "providerVoiceId": "male_1",
      "sampleStorageKey": null,
      "isActive": true
    }
  ]
}
```

---

### Дополнительные требования

- [x] Требуется авторизация
- [ ] Требуется проверка прав доступа (только админ?)
- [ ] Требуется rate limiting
- [x] Требуется логирование
- [ ] Требуется кэширование

### Примечания

1. **Структура файлов:**
   ```
   public/cache/voices/
   ├── audio/
   │   ├── narrator_1.mp3
   │   ├── narrator_2.mp3
   │   ├── male_1.mp3
   │   ├── male_2.mp3
   │   ├── female_1.mp3
   │   └── female_2.mp3
   └── meta/
       └── voice-metadata.json
   ```

2. **Метаданные:**
   - Если в `voice-metadata.json` есть запись с `audioFile` совпадающим с найденным файлом, используются эти метаданные
   - Если метаданных нет, создаются базовые:
     - `name`: "{Роль} {Индекс}" (например, "Диктор 1")
     - `language`: "ru" (по умолчанию)
     - `style`: "default"
     - `provider`: "local"

3. **Обновление существующих:**
   - Если голос с таким `providerVoiceId` уже существует:
     - При `force = false`: пропускается
     - При `force = true`: обновляется (name, language, style из метаданных)

4. **Обработка ошибок:**
   - Если файл не может быть прочитан, добавляется в `errors`, но процесс продолжается
   - Если метаданные невалидны, используется базовая информация из имени файла
