## ТЗ: Фильтрация голосов по роли

**Метод:** GET  
**Путь:** `/api/voices`  
**Описание:** Обновление существующего endpoint для поддержки фильтрации по роли голоса (Диктор, Мужской голос, Женский голос).

---

### Request

#### Headers
```
Authorization: Bearer <token>  # требуется авторизация
```

#### Query Parameters
| Параметр | Тип | Описание | Обязательный | Возможные значения |
|----------|-----|----------|--------------|-------------------|
| `language` | string | Язык голоса | Нет | `ru`, `en`, и т.д. |
| `gender` | string | Пол голоса | Нет | `male`, `female`, `neutral` |
| `style` | string | Стиль голоса | Нет | Любая строка |
| `role` | string | Роль голоса | Нет | `narrator` (Диктор), `actor` (Актер) |

---

### Response

#### Success Response (200)
```json
{
  "voices": [
    {
      "id": "clx123...",
      "name": "Диктор 1",
      "role": "narrator",
      "gender": "neutral",
      "language": "ru",
      "style": "default",
      "provider": "local",
      "isActive": true,
      "hasSample": true,
      "characterDescription": "Описание характера"
    },
    {
      "id": "clx456...",
      "name": "Мужской голос 1",
      "role": "actor",
      "gender": "male",
      "language": "ru",
      "style": "dramatic",
      "provider": "local",
      "isActive": true,
      "hasSample": true,
      "characterDescription": null
    }
  ]
}
```

#### Error Responses

**400 Bad Request**
```json
{
  "error": {
    "code": "INVALID_ROLE",
    "message": "Invalid role value. Allowed values: narrator, actor"
  }
}
```

**401 Unauthorized**
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required"
  }
}
```

---

### Примеры использования

#### Получить все голоса
```bash
GET /api/voices
```

#### Получить только дикторов
```bash
GET /api/voices?role=narrator
```

#### Получить только актеров
```bash
GET /api/voices?role=actor
```

#### Получить мужские голоса актеров
```bash
GET /api/voices?role=actor&gender=male
```

#### Получить женские голоса актеров
```bash
GET /api/voices?role=actor&gender=female
```

#### Получить русскоязычных дикторов
```bash
GET /api/voices?role=narrator&language=ru
```

#### Комбинированная фильтрация
```bash
GET /api/voices?role=actor&gender=male&language=ru&style=dramatic
```

---

### Логика фильтрации

1. **Роль `narrator` (Диктор):**
   - Возвращает голоса с `role = 'narrator'`
   - Обычно имеют `gender = 'neutral'`
   - Используются для повествования от автора

2. **Роль `actor` (Актер):**
   - Возвращает голоса с `role = 'actor'`
   - Могут иметь `gender = 'male'` или `gender = 'female'`
   - Используются для озвучивания персонажей

3. **Комбинирование фильтров:**
   - Все фильтры применяются через AND (логическое И)
   - Если указан `role=actor` и `gender=male`, вернутся только мужские голоса актеров

---

### Сортировка

Голоса сортируются в следующем порядке:
1. По роли (`role`) - сначала `narrator`, затем `actor`
2. По языку (`language`)
3. По имени (`name`)

---

### Дополнительные требования

- [x] Требуется авторизация
- [ ] Требуется проверка прав доступа
- [ ] Требуется rate limiting
- [ ] Требуется логирование
- [ ] Требуется кэширование (опционально)

### Примечания

1. **Обратная совместимость:**
   - Если параметр `role` не указан, возвращаются все голоса (как сейчас)
   - Существующие запросы продолжат работать без изменений

2. **Валидация:**
   - Если указан недопустимый `role`, возвращается ошибка 400
   - Допустимые значения: `narrator`, `actor`

3. **Производительность:**
   - Индекс на поле `role` обеспечит быстрый поиск
   - Составной индекс `(role, gender, language)` может улучшить производительность при комбинированных фильтрах
