# Инспекция пайплайна Stage 0–3: почему текст без ударений и обработки

## Цепочка данных

```
Stage0 (FormatDetector → FormatParser → TextExtractor)
    → raw lines
Stage1 (ChapterParser → LineTypeParser)
    → Line[] с original, type
Stage2 (SpeakerResolver)
    → Line[] с speaker
Stage3 (SegmentAnalyzer → SegmentTextAdapter → StressPlaceholder → TTSDirector)
    → rendered[] с tts_text, segments, emotion
_replace_book_lines_and_tasks
    → Line в БД, TTSTask.payload = { text: tts_text, ... }
process_book_stage4 / tts-next
    → payload["text"] в Stage4 → TTS Engine
```

## Найденные проблемы

### 1. ✅ **pymorphy3 добавлен** (исправлено)

**Файл:** `core/pipeline/stage1_5_stress.py`

```python
_spec = importlib.util.find_spec("pymorphy3")
_morph = None
if _spec is not None:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()

def lemmatize(word: str) -> str | None:
    if _morph is None:
        return None
    ...
```

- `pymorphy3` **нет в** `requirements.txt`.
- Без морфологического анализатора `lemmatize()` всегда возвращает `None`.
- `STRESS_DICT` ищет лемму слова; без леммы поиск не срабатывает.
- В результате `process_segment_text()` не ставит ударения, возвращает исходный текст.

**Выполнено:** добавлено в `requirements.txt`.

---

### 2. ✅ **TTSDirector-анализ передаётся в TTSTask** (исправлено)

**Файл:** `core/services/pipeline_service.py`, `run_stage3`

- `TTSDirector` анализирует ремарки («прошептал», «закричал», «грустно» и т.п.) и заполняет `segment.tts_meta` (volume, emotion, tempo).
- `_aggregate_emotion_from_segments()` агрегирует `tts_meta` в формат emotion для payload.
- Результат передаётся в `TTSTask.payload["emotion"]`.

---

### 3. ⚠️ **SpeechDirector не вызывается**

**Файл:** `core/pipeline/stage3_speech_director.py`

- Модуль `SpeechDirector` есть, но **не вызывается** в `run_stage3`.
- Используется только `TTSDirector`.
- Логика просодии, `respect_stress` и т.п. не применяется.

**Решение:** либо интегрировать `SpeechDirector` в цепочку Stage3, либо удалить, если не используется.

---

### 4. ℹ️ **Ремарки в тексте TTS**

- Ремарки оставлены в `tts_text_line` по требованию — озвучиваются вместе с речью.

---

### 5. ⚠️ **Проверка поддержки ударений в TTS**

- В Stage 1.5 используется символ ударения `\u0301` (combining acute accent).
- Необходимо убедиться, что Coqui XTTS v2 **использует** этот символ при синтезе.
- Если TTS игнорирует или некорректно обрабатывает `\u0301`, результат будет без ударений.

---

## Корректность передачи `tts_text`

| Этап | Действие |
|------|----------|
| `run_stage3` | `tts_text_line = " ".join(seg["tts_text"] for seg in serialized_segments)` — текст после StressPlaceholder |
| `_replace_book_lines_and_tasks` | `payload["text"] = line_payload.get("tts_text") or db_line.original` |
| `process_book_stage4` | `payload_row["text"]` передаётся в Stage4 |
| `tts-next` | `payload["text"]` в TTSLeaseResponse |

Вывод: в payload действительно уходит `tts_text` (строка 153 в `pipeline_service.py`).  
Проблема в том, что из‑за отсутствия `pymorphy3` StressPlaceholder не меняет текст, и `tts_text` фактически равен адаптированному `original_text` без ударений.

---

## Рекомендуемые действия / Выполнено

1. ✅ Добавить `pymorphy3` и словари в `requirements.txt`.
2. ✅ Передать сегментные `tts_meta` в payload через `_aggregate_emotion_from_segments()`.
3. ℹ️ Ремарки оставлены в тексте TTS.
4. Уточнить поддержку `\u0301` в Coqui XTTS v2 и при необходимости документировать/обойти.
5. Решить судьбу `SpeechDirector`: либо встроить в пайплайн, либо удалить.
