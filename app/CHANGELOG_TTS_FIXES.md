# Исправления TTS системы - История изменений

## Дата: 13 февраля 2026

### Проблемы, которые были решены

1. **Не передавались параметры `voices` и `language` на Stage4_service**
2. **Низкое качество синтеза речи** - использовался деградированный backend (espeak) вместо Coqui XTTS v2
3. **Таймауты при синтезе длинных текстов** - "Read timed out" ошибки
4. **Разрывы соединения** - "Connection aborted" ошибки при обработке больших аудиофайлов
5. **Падение контейнера stage4-tts** - ошибка "Cannot allocate memory" из-за watchfiles

---

## Внесенные изменения

### 1. Передача параметров `language` и `audio_config` через весь пайплайн

#### Файл: `app/api/routes/internal.py`
- Добавлена функция `_extract_language()` для извлечения языка из `audio_config`
- В `process_book_stage4()` добавлена передача `language` и `effective_audio_config` в Stage4
- Параметры теперь корректно передаются через цепочку: API → Stage4 → TTS Engine

**Изменения:**
```python
# Добавлена функция извлечения языка
def _extract_language(audio_config: dict) -> str | None:
    # Извлекает язык из audio_config.engine.language

# В process_book_stage4 добавлено:
effective_audio_config = _effective_audio_config(user_audio.config if user_audio else None)
language = _extract_language(effective_audio_config)
# Передача в Stage4:
"audio_config": effective_audio_config,
"language": language,
```

#### Файл: `app/stage4_service/app.py`
- Добавлена логика извлечения `language` из `audio_config` в `process_next_task()`
- `language` передается в `TTSRequest` для дальнейшей обработки

#### Файл: `app/core/integrations/stage4_tts_client.py`
- Метод `synthesize_line()` обновлен для приема и передачи `audio_config` и `language`

---

### 2. Исправление инициализации Coqui XTTS v2

#### Файл: `app/tts_engine_service/app.py`

**a) Обход интерактивного соглашения Coqui:**
- Добавлено `os.environ["COQUI_TOS_AGREED"] = "1"` перед импортом TTS
- Это предотвращает блокировку при первом запуске

**b) Исправление проблемы с PyTorch 2.6+ `weights_only`:**
- Реализован monkey patch для `torch.load` с явной установкой `weights_only=False`
- PyTorch 2.6+ по умолчанию требует `weights_only=True`, что блокирует загрузку моделей Coqui

**c) Исправление типа параметра `top_k`:**
- В функции `_resolve_xtts_params()` добавлено приведение `top_k` к целому числу (`as_int=True`)
- Библиотека `transformers` требует строго целочисленное значение

**d) Улучшение разрешения путей к голосовым образцам:**
- Функция `_resolve_coqui_speaker_wav()` обновлена для проверки:
  1. Явно переданного `request.voice_sample`
  2. Путей из `audio_config.voices[speaker]`
  3. Стандартных путей из `TTS_VOICES_ROOT`

**Изменения:**
```python
# Monkey patch для torch.load
original_load = torch.load
def patched_load(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return original_load(*args, **kwargs)
torch.load = patched_load

# Исправление top_k
_num("top_k", 1, 400, as_int=True)  # Приведение к int
```

---

### 3. Исправление зависимостей для Coqui TTS

#### Файл: `app/tts_engine_service/requirements.txt`
- Добавлен `transformers==4.35.0` - исправляет ошибку `BeamSearchScorer`
- Добавлен `torchcodec` - требуется для `torchaudio` и Coqui
- Добавлен `torchaudio` - зависимость для Coqui

**Добавленные зависимости:**
```
transformers==4.35.0
torchcodec
torchaudio
```

---

### 4. Увеличение таймаутов для длинных текстов

#### Файл: `app/docker-compose.yml`
- Добавлена переменная окружения `EXTERNAL_TTS_TIMEOUT_SEC=300` для сервиса `stage4-tts`
- Таймаут увеличен с 60 до 300 секунд (5 минут)
- Это позволяет обрабатывать длинные тексты без ошибок таймаута

**Изменения:**
```yaml
stage4-tts:
  environment:
    - EXTERNAL_TTS_TIMEOUT_SEC=300  # Было 60 по умолчанию
```

---

### 5. Исправление проблемы с памятью в stage4-tts

#### Файл: `app/docker-compose.yml`
- Убран флаг `--reload` из команды запуска `stage4-tts`
- `--reload` использует watchfiles, который вызывает ошибку "Cannot allocate memory"
- В production окружении `--reload` не нужен

**Изменения:**
```yaml
# Было:
command: python3 -m uvicorn stage4_service.app:app --host 0.0.0.0 --port 8010 --reload

# Стало:
command: python3 -m uvicorn stage4_service.app:app --host 0.0.0.0 --port 8010
```

---

### 6. Потоковая загрузка больших аудиофайлов

#### Файл: `app/stage4_service/synth.py`
- Добавлен `stream=True` в запрос `requests.post()`
- Изменена запись файла с `response.content` на потоковую запись через `iter_content()`
- Это предотвращает разрыв соединения при передаче больших аудиофайлов

**Изменения:**
```python
# Было:
response = requests.post(..., timeout=self.timeout_sec)
output_path.write_bytes(response.content)

# Стало:
response = requests.post(..., timeout=self.timeout_sec, stream=True)
with output_path.open("wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)
```

---

### 7. Переменные окружения для Coqui

#### Файл: `app/docker-compose.yml`
- Добавлена переменная `COQUI_TOS_AGREED=1` для сервиса `tts-engine`
- Это дублирует установку в коде для надежности

**Изменения:**
```yaml
tts-engine:
  environment:
    - COQUI_TOS_AGREED=1  # Согласие с лицензией Coqui
```

---

## Результаты

После всех исправлений:

1. ✅ Параметры `language` и `voices` корректно передаются через весь пайплайн
2. ✅ Coqui XTTS v2 успешно инициализируется и используется вместо espeak
3. ✅ Настройки из `audio.yaml` применяются корректно (язык, голоса, параметры XTTS)
4. ✅ Длинные тексты обрабатываются без таймаутов (таймаут 300 секунд)
5. ✅ Большие аудиофайлы передаются без разрывов соединения (потоковая загрузка)
6. ✅ Контейнер stage4-tts стабильно работает без падений

---

## Конфигурация audio.yaml

Система использует следующие настройки из `audio.yaml`:

```yaml
engine:
  type: xtts_v2
  language: ru
  device: auto

voices:
  narrator: storage/voices/narrator.wav
  male: storage/voices/male.wav
  female: storage/voices/female.wav

xtts:
  temperature: 1
  top_k: 50
  top_p: 1
  repetition_penalty: 2.8
  speed_base: 1.2
```

Все эти параметры теперь корректно применяются при синтезе речи.

---

## Технические детали

### Архитектура пайплайна TTS:
1. **API** (`app/api/routes/internal.py`) - принимает запросы, извлекает конфигурацию
2. **Stage4 TTS** (`app/stage4_service/`) - оркестрация, сохранение файлов
3. **TTS Engine** (`app/tts_engine_service/`) - непосредственно синтез речи (Coqui/espeak/mock)

### Порядок передачи параметров:
```
API → Stage4 → TTS Engine
  ↓      ↓         ↓
language, audio_config → TTSRequest → SynthesizeRequest
```

### Backend приоритеты:
1. Coqui XTTS v2 (если доступен)
2. Espeak (если Coqui недоступен и разрешен fallback)
3. Mock (если ничего не доступно)

---

## Команды для перезапуска

После изменений необходимо перезапустить сервисы:

```bash
cd app
docker-compose down
docker-compose up -d --build
```

Или перезапустить отдельные сервисы:

```bash
docker-compose restart stage4-tts
docker-compose restart tts-engine
```

---

## Проверка работоспособности

### Проверка здоровья TTS Engine:
```bash
curl http://localhost:8020/health
```

Ожидаемый ответ должен содержать:
- `"coqui_ready": true`
- `"coqui_error": null`
- `"active_backend": "coqui"`

### Проверка Stage4 TTS:
```bash
curl http://localhost:8010/health
```

---

## Известные ограничения

1. **Длина текста**: Coqui XTTS имеет ограничение ~182 символа для русского языка. Более длинные тексты могут быть обрезаны (предупреждение в логах).

2. **Время синтеза**: Синтез длинных текстов может занимать 30-50 секунд. Таймаут установлен в 300 секунд для надежности.

3. **Память**: Coqui модель требует значительный объем памяти. Убедитесь, что у контейнера достаточно ресурсов.

---

## Файлы, которые были изменены

1. `app/api/routes/internal.py` - передача параметров
2. `app/stage4_service/app.py` - обработка параметров
3. `app/stage4_service/synth.py` - потоковая загрузка
4. `app/core/integrations/stage4_tts_client.py` - клиент для Stage4
5. `app/tts_engine_service/app.py` - основная логика TTS Engine
6. `app/tts_engine_service/requirements.txt` - зависимости
7. `app/docker-compose.yml` - конфигурация Docker

---

## Заключение

Все критические проблемы с TTS синтезом были решены. Система теперь использует высококачественный Coqui XTTS v2 с корректной передачей всех параметров конфигурации. Качество синтеза речи значительно улучшилось по сравнению с деградированным espeak backend.
