# Как добавить голоса актеров вручную

## Шаги для добавления голоса

### 1. Добавьте аудио файл
Поместите аудио файл в папку `audio/`:
```
public/cache/voices/audio/voice-1-sample.mp3
```

**Рекомендации:**
- Формат: MP3 (предпочтительно), WAV, OGG
- Размер: до 5MB на файл
- Длительность: 5-30 секунд для предпросмотра

### 2. Обновите метаданные
Откройте файл `meta/voice-metadata.json` и добавьте запись о голосе:

```json
{
  "voices": [
    {
      "id": "voice-1",
      "name": "Название голоса",
      "description": "Описание голоса",
      "gender": "male",
      "ageRange": "adult",
      "language": "ru",
      "audioFile": "/cache/voices/audio/voice-1-sample.mp3",
      "previewText": "Текст для предпросмотра голоса",
      "tags": ["тег1", "тег2"],
      "createdAt": "2026-02-12T00:00:00Z",
      "updatedAt": "2026-02-12T00:00:00Z"
    }
  ],
  "metadata": {
    "version": "1.0.0",
    "lastSync": null,
    "totalVoices": 1
  }
}
```

### 3. Обновите счетчик
Не забудьте обновить `totalVoices` в метаданных на актуальное количество голосов.

## Пример использования в коде

```typescript
import { getAllVoices, getVoiceById, getVoiceAudioUrl } from '@/lib/voice-cache';

// Получить все голоса
const voices = await getAllVoices();

// Получить голос по ID
const voice = await getVoiceById('voice-1');

// Получить URL аудио файла
const audioUrl = getVoiceAudioUrl(voice.audioFile);
```

## Структура файлов

```
public/cache/voices/
├── audio/                    # Аудио файлы
│   ├── .gitkeep
│   └── voice-1-sample.mp3   # Ваши файлы здесь
├── meta/                     # Метаданные
│   ├── .gitkeep
│   ├── voice-metadata.json  # Основной файл метаданных
│   └── voice-metadata.example.json  # Пример
├── README.md
└── HOW_TO_ADD_VOICES.md     # Этот файл
```

## Важно

- Аудио файлы **не попадают в git** (добавлены в .gitignore)
- Метаданные **попадают в git** (для синхронизации между разработчиками)
- После добавления файлов вручную, они будут доступны через `/cache/voices/audio/...`
- В будущем файлы будут загружаться автоматически через API
