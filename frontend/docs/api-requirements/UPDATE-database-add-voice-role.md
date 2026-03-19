## ТЗ: Добавление поля role в модель Voice

**Тип:** Миграция базы данных  
**Описание:** Добавить поле `role` в модель `Voice` для разделения голосов на роли: Диктор, Мужской голос, Женский голос.

---

### Изменения в схеме Prisma

#### 1. Добавить enum VoiceRole

```prisma
enum VoiceRole {
  narrator  // Диктор
  actor     // Актер (для мужских и женских голосов)
}
```

#### 2. Обновить модель Voice

Добавить поле `role` в модель `Voice`:

```prisma
model Voice {
  id                  String      @id @default(cuid())
  name                String
  role                VoiceRole   @default(actor)  // НОВОЕ ПОЛЕ
  gender              VoiceGender
  language            String
  style               String
  provider            String
  providerVoiceId     String
  sampleStorageKey    String?
  characterDescription String?
  isActive            Boolean     @default(true)
  createdAt           DateTime    @default(now())
  updatedAt           DateTime    @updatedAt

  projects ProjectVoice[]

  @@unique([provider, providerVoiceId])
  @@index([role])  // НОВЫЙ ИНДЕКС
}
```

---

### Миграция данных

#### Скрипт миграции данных (SQL)

```sql
-- Добавить enum тип
CREATE TYPE "VoiceRole" AS ENUM ('narrator', 'actor');

-- Добавить колонку role с дефолтным значением
ALTER TABLE "Voice" ADD COLUMN "role" "VoiceRole" NOT NULL DEFAULT 'actor';

-- Обновить существующие записи на основе gender
-- Дикторы обычно имеют gender = 'neutral'
UPDATE "Voice" SET "role" = 'narrator' WHERE "gender" = 'neutral';

-- Для остальных (male/female) оставляем 'actor'
-- Это уже дефолтное значение, но можно явно указать:
UPDATE "Voice" SET "role" = 'actor' WHERE "gender" IN ('male', 'female');

-- Создать индекс для быстрого поиска по роли
CREATE INDEX "Voice_role_idx" ON "Voice"("role");
```

---

### Обновление API

#### 1. Обновить DTO для фильтрации

В `voices.controller.ts` и `voices.service.ts` добавить поддержку фильтрации по `role`:

```typescript
// В voices.service.ts
async list(filters: { 
  language?: string; 
  gender?: string; 
  style?: string;
  role?: string;  // НОВЫЙ ФИЛЬТР
}) {
  const where: { 
    isActive: boolean; 
    language?: string; 
    gender?: VoiceGender; 
    style?: string;
    role?: VoiceRole;  // НОВОЕ ПОЛЕ
  } = {
    isActive: true,
  };
  if (filters.language != null && filters.language !== '') 
    where.language = filters.language;
  if (filters.gender != null && filters.gender !== '') 
    where.gender = filters.gender as VoiceGender;
  if (filters.style != null && filters.style !== '') 
    where.style = filters.style;
  if (filters.role != null && filters.role !== '') 
    where.role = filters.role as VoiceRole;  // НОВАЯ ПРОВЕРКА

  return this.prisma.voice.findMany({
    where,
    orderBy: [{ role: 'asc' }, { language: 'asc' }, { name: 'asc' }],
  });
}
```

#### 2. Обновить контроллер

```typescript
// В voices.controller.ts
@Get()
async list(
  @Query('language') language?: string, 
  @Query('gender') gender?: string, 
  @Query('style') style?: string,
  @Query('role') role?: string  // НОВЫЙ ПАРАМЕТР
) {
  const items = await this.voices.list({ language, gender, style, role });
  return {
    voices: items.map((v) => ({
      id: v.id,
      name: v.name,
      role: v.role,  // НОВОЕ ПОЛЕ В ОТВЕТЕ
      gender: v.gender,
      language: v.language,
      style: v.style,
      provider: v.provider,
      isActive: v.isActive,
      hasSample: Boolean(v.sampleStorageKey),
      characterDescription: v.characterDescription ?? null,
    })),
  };
}
```

---

### Маппинг ролей при синхронизации

При синхронизации из файловой системы:

- Файл `narrator_*.mp3` → `role = "narrator"`, `gender = "neutral"`
- Файл `male_*.mp3` → `role = "actor"`, `gender = "male"`
- Файл `female_*.mp3` → `role = "actor"`, `gender = "female"`

---

### Примеры использования

#### Получить только дикторов
```
GET /api/voices?role=narrator
```

#### Получить только актеров
```
GET /api/voices?role=actor
```

#### Получить мужские голоса актеров
```
GET /api/voices?role=actor&gender=male
```

---

### Примечания

1. **Обратная совместимость:**
   - Дефолтное значение `role = 'actor'` обеспечивает обратную совместимость
   - Существующие голоса автоматически получат `role = 'actor'`
   - Дикторы (с `gender = 'neutral'`) будут обновлены на `role = 'narrator'`

2. **Индексация:**
   - Индекс на поле `role` улучшит производительность фильтрации
   - Можно использовать составной индекс `(role, gender)` если нужно

3. **Валидация:**
   - При создании/обновлении голоса нужно валидировать соответствие `role` и `gender`:
     - `role = 'narrator'` → `gender` должен быть `'neutral'`
     - `role = 'actor'` → `gender` должен быть `'male'` или `'female'`
