# core/pipeline/stage3_emotion.py
"""
Stage 3 — EmotionResolver (обёртка над SpeechDirector).
Сохраняет обратную совместимость с существующим API.
"""
try:
    from .stage3_speech_director import SpeechDirector
    _USE_SPEECH_DIRECTOR = True
except ImportError:
    _USE_SPEECH_DIRECTOR = False

import re
from core.models import Line, UserBookFormat, EmotionProfile


class EmotionResolver:
    """
    Stage 3 — EmotionResolver.
    Использует SpeechDirector для расширенного анализа ремарок и пунктуации.
    """

    EXCLAMATION_RE = re.compile(r"!+")
    QUESTION_RE = re.compile(r"\?+")
    ELLIPSIS_RE = re.compile(r"\.\.\.|…")
    CAPS_RE = re.compile(r"\b[А-ЯЁ]{3,}\b")

    def __init__(self):
        self._speech_director = SpeechDirector() if _USE_SPEECH_DIRECTOR else None

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        """Обработка эмоций для всех строк"""
        # Если доступен SpeechDirector — используем его
        if self._speech_director:
            return self._speech_director.process(ubf)

        # Fallback на базовую логику
        for line in ubf.lines:
            line.emotion = self._analyze(line)
        return ubf

    def _analyze(self, line: Line) -> EmotionProfile:
        """Анализ эмоций для строки (fallback)"""
        profile = EmotionProfile()

        if line.type == "narrator":
            profile.energy = 0.95
            profile.tempo = 0.95
            profile.pitch = 0.0
        else:
            profile.energy = 1.0
            profile.tempo = 1.0
            profile.pitch = 0.0

        text = line.original

        if self.EXCLAMATION_RE.search(text):
            profile.energy += 0.2
            profile.pitch += 0.1

        if self.QUESTION_RE.search(text):
            profile.pitch += 0.2
            profile.tempo += 0.05

        if self.ELLIPSIS_RE.search(text):
            profile.tempo -= 0.15
            profile.pause_after += 300
            profile.pause_before += 100

        if self.CAPS_RE.search(text):
            profile.energy += 0.25
            profile.pitch += 0.15

        if hasattr(line, 'is_segment') and line.is_segment:
            if hasattr(line, 'segment_index') and hasattr(line, 'segment_total'):
                if line.segment_index == line.segment_total - 1:
                    profile.pause_after += 200
                elif line.segment_index > 0:
                    profile.pause_before += 50

        return self._clamp(profile)

    @staticmethod
    def _clamp(p: EmotionProfile) -> EmotionProfile:
        """Ограничение значений"""
        p.energy = max(0.5, min(p.energy, 1.5))
        p.tempo = max(0.7, min(p.tempo, 1.3))
        p.pitch = max(-0.5, min(p.pitch, 0.5))
        p.pause_before = min(p.pause_before, 1000)
        p.pause_after = min(p.pause_after, 1000)
        return p