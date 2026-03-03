# Шаблон ТЗ для API Endpoint

## ТЗ: [Название endpoint'а]

**Метод:** [GET/POST/PUT/DELETE/PATCH]  
**Путь:** `/api/v1/[путь]`  
**Описание:** [Краткое описание что делает endpoint и зачем он нужен]

---

### Request

#### Headers
```
Authorization: Bearer <token>  # если требуется авторизация
Content-Type: application/json
```

#### Path Parameters
| Параметр | Тип | Описание | Обязательный |
|----------|-----|----------|--------------|
| `id` | string | ID ресурса | Да |

#### Query Parameters
| Параметр | Тип | Описание | Обязательный | По умолчанию |
|----------|-----|----------|--------------|--------------|
| `page` | number | Номер страницы | Нет | 1 |
| `limit` | number | Количество элементов | Нет | 10 |

#### Request Body
```json
{
  "field1": "string",
  "field2": 123,
  "field3": true
}
```

**Схема валидации:**
- `field1`: string, обязательное, min 1, max 255
- `field2`: number, обязательное, min 0
- `field3`: boolean, необязательное

---

### Response

#### Success Response (200)
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "field1": "value",
    "field2": 123,
    "createdAt": "2026-02-12T21:00:00Z"
  },
  "message": "Operation completed successfully"
}
```

#### Error Responses

**400 Bad Request**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "field": "field1",
        "message": "Field is required"
      }
    ]
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

**404 Not Found**
```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found"
  }
}
```

**500 Internal Server Error**
```json
{
  "success": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Internal server error"
  }
}
```

---

### Примеры использования

#### Пример запроса
```bash
curl -X POST https://api.example.com/api/v1/resource \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "field1": "example",
    "field2": 42
  }'
```

#### Пример успешного ответа
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "field1": "example",
    "field2": 42,
    "createdAt": "2026-02-12T21:00:00Z"
  },
  "message": "Resource created successfully"
}
```

---

### Дополнительные требования

- [ ] Требуется авторизация
- [ ] Требуется проверка прав доступа
- [ ] Требуется rate limiting
- [ ] Требуется логирование
- [ ] Требуется кэширование

### Примечания
[Любые дополнительные замечания, особенности реализации, зависимости от других endpoint'ов и т.д.]
