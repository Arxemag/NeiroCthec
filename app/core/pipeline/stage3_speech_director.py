# core/pipeline/stage3_speech_director.py
"""
Stage 3 — Speech Director.
Анализирует ремарки и пунктуацию для определения КАК читать текст.
Не меняет текст, только добавляет параметры озвучки.
"""
import re
import builtins
from dataclasses import dataclass, field
from typing import List, Optional

from core.models import Line, UserBookFormat, EmotionProfile


def _safe_print(*args, **kwargs):
    """Print wrapper that ignores ValueError."""
    try:
        builtins.print(*args, **kwargs)
    except ValueError:
        pass


@dataclass
class SpeechMeta:
    """Метаданные для озвучки сегмента"""
    energy: float = 1.0
    tempo: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0
    pause_before: int = 0
    pause_after: int = 0
    whisper: bool = False
    respect_stress: bool = False
    tags: List[str] = field(default_factory=list)


# Правила для ремарок (паттерн, параметры, тег)
REMARK_RULES = [
    # Шёпот
    (
        re.compile(r"\b(прошептал[а]?|шёпотом|тихо сказал[а]?|едва слышно)\b", re.I),
        {'whisper': True, 'volume': 0.4, 'energy': 0.6, 'tempo': 0.85},
        "remark:whisper"
    ),
    # Крик
    (
        re.compile(r"\b(крикнул[а]?|закричал[а]?|заорал[а]?|вскричал[а]?|взревел[а]?)\b", re.I),
        {'volume': 1.4, 'energy': 1.3, 'pitch': 0.2},
        "remark:shout"
    ),
    # Усталость / бормотание
    (
        re.compile(r"\b(устало сказал[а]?|пробормотал[а]?|выдохнул[а]?|вздохнул[а]?)\b", re.I),
        {'tempo': 0.8, 'energy': 0.7},
        "remark:tired"
    ),
    # Злость
    (
        re.compile(r"\b(рявкнул[а]?|огрызнул[а]?сь|процедил[а]?|прорычал[а]?)\b", re.I),
        {'energy': 1.25, 'pitch': -0.1, 'tempo': 1.1},
        "remark:angry"
    ),
    # Удивление
    (
        re.compile(r"\b(удивлённо|изумлённо|поражённо|ошарашенно)\b", re.I),
        {'pitch': 0.15, 'energy': 1.1},
        "remark:surprised"
    ),
    # Грусть
    (
        re.compile(r"\b(грустно|печально|тоскливо|понуро)\b", re.I),
        {'energy': 0.75, 'tempo': 0.85, 'pitch': -0.1},
        "remark:sad"
    ),
    # Радость
    (
        re.compile(r"\b(радостно|весело|восторженно|счастливо)\b", re.I),
        {'energy': 1.2, 'tempo': 1.1, 'pitch': 0.1},
        "remark:happy"
    ),
    # Ирония / сарказм
    (
        re.compile(r"\b(саркастически|иронично|насмешливо|язвительно)\b", re.I),
        {'tempo': 0.9, 'pitch': 0.05},
        "remark:sarcastic"
    ),
]

# Паттерны пунктуации
EXCLAMATION_RE = re.compile(r"!+")
QUESTION_RE = re.compile(r"\?+")
ELLIPSIS_RE = re.compile(r"\.\.\.|…")
DOUBLE_DASH_RE = re.compile(r"[—–−]{2,}")


class SpeechDirector:
    """
    Stage 3 — Speech Director.
    Анализирует текст и определяет параметры озвучки.
    """

    def __init__(self, apply_to_emotion: bool = True):
        self.apply_to_emotion = apply_to_emotion
        self.stats = {
            'total_processed': 0,
            'remarks_found': 0,
            'punctuation_applied': 0,
        }

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        """Обрабатывает все строки"""
        _safe_print(f"\nStage 3: Speech Director")

        for line in ubf.lines:
            self._process_line(line)
            self.stats['total_processed'] += 1

        self._log_statistics()
        return ubf

    def _process_line(self, line: Line):
        """Обрабатывает одну строку"""
        meta = SpeechMeta(tags=[])
        text = line.original or ""

        # Базовые настройки по типу
        if line.type == "dialogue":
            meta.energy = 1.0
            meta.tempo = 1.0
            meta.tags.append("base:dialogue")
        else:
            meta.energy = 0.95
            meta.tempo = 0.95
            meta.tags.append("base:narration")

        # Анализ ремарок (приоритет над пунктуацией)
        remark_applied = False
        for pattern, params, tag in REMARK_RULES:
            if pattern.search(text):
                for k, v in params.items():
                    setattr(meta, k, v)
                meta.tags.append(tag)
                meta.tags.append("source:remark")
                remark_applied = True
                self.stats['remarks_found'] += 1
                break

        # Анализ пунктуации (накладывается поверх)
        punct_applied = False

        if EXCLAMATION_RE.search(text):
            meta.energy += 0.15
            meta.pitch += 0.1
            meta.tags.append("punct:exclamation")
            punct_applied = True

        if QUESTION_RE.search(text):
            meta.pitch += 0.2
            meta.tags.append("punct:question")
            punct_applied = True

        if ELLIPSIS_RE.search(text):
            meta.tempo -= 0.1
            meta.pause_after += 300
            meta.tags.append("punct:ellipsis")
            punct_applied = True

        if DOUBLE_DASH_RE.search(text):
            meta.pause_before += 200
            meta.tags.append("punct:pause")
            punct_applied = True

        if punct_applied:
            self.stats['punctuation_applied'] += 1

        # Clamp значений
        meta = self._clamp(meta)

        # Применяем к EmotionProfile строки
        if self.apply_to_emotion:
            self._apply_to_emotion_profile(line, meta)

    def _clamp(self, meta: SpeechMeta) -> SpeechMeta:
        """Ограничивает значения в допустимых пределах"""
        meta.energy = max(0.5, min(meta.energy, 1.5))
        meta.tempo = max(0.7, min(meta.tempo, 1.3))
        meta.pitch = max(-0.5, min(meta.pitch, 0.5))
        meta.volume = max(0.3, min(meta.volume, 1.5))
        meta.pause_before = min(meta.pause_before, 1500)
        meta.pause_after = min(meta.pause_after, 1500)
        return meta

    def _apply_to_emotion_profile(self, line: Line, meta: SpeechMeta):
        """Применяет SpeechMeta к EmotionProfile строки"""
        if line.emotion is None:
            line.emotion = EmotionProfile(
                energy=meta.energy,
                tempo=meta.tempo,
                pitch=meta.pitch,
                pause_before=meta.pause_before,
                pause_after=meta.pause_after,
            )
        else:
            # Обновляем существующий профиль
            line.emotion.energy = meta.energy
            line.emotion.tempo = meta.tempo
            line.emotion.pitch = meta.pitch
            line.emotion.pause_before = max(line.emotion.pause_before, meta.pause_before)
            line.emotion.pause_after = max(line.emotion.pause_after, meta.pause_after)

    def _log_statistics(self):
        """Логирование статистики"""
        _safe_print(f"  Обработано строк: {self.stats['total_processed']}")
        _safe_print(f"  Найдено ремарок: {self.stats['remarks_found']}")
        _safe_print(f"  Применена пунктуация: {self.stats['punctuation_applied']}")


# Альтернативное имя для совместимости
EmotionResolver = SpeechDirector
