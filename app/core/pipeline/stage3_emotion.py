# core/pipeline/stage3_emotion.py
import re
from typing import List

from core.models import Line, UserBookFormat, EmotionProfile


class EmotionResolver:
    """
    Stage 3 — EmotionResolver
    Работает с вашей моделью EmotionProfile (с pause_before и pause_after)
    """

    EXCLAMATION_RE = re.compile(r"!+")
    QUESTION_RE = re.compile(r"\?+")
    ELLIPSIS_RE = re.compile(r"\.\.\.|…")
    CAPS_RE = re.compile(r"\b[А-ЯЁ]{3,}\b")

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        """Обработка эмоций для всех строк"""
        for line in ubf.lines:
            line.emotion = self._analyze(line)
        return ubf

    def _analyze(self, line: Line) -> EmotionProfile:
        """Анализ эмоций для строки"""
        profile = EmotionProfile()

        if line.type == "narrator":
            # Базовые настройки для повествования
            profile.energy = 0.95
            profile.tempo = 0.95
            profile.pitch = 0.0
        else:
            # Базовые настройки для диалога
            profile.energy = 1.0
            profile.tempo = 1.0
            profile.pitch = 0.0

        text = line.original

        # Анализ текстовых маркеров
        if self.EXCLAMATION_RE.search(text):
            profile.energy += 0.2
            profile.pitch += 0.1

        if self.QUESTION_RE.search(text):
            profile.pitch += 0.2
            profile.tempo += 0.05

        if self.ELLIPSIS_RE.search(text):
            profile.tempo -= 0.15
            profile.pause_after += 300  # 🔥 Используем ваше поле pause_after
            profile.pause_before += 100  # 🔥 И pause_before

        if self.CAPS_RE.search(text):
            profile.energy += 0.25
            profile.pitch += 0.15

        # 🔥 ОСОБАЯ ЛОГИКА ДЛЯ СЕГМЕНТОВ
        if hasattr(line, 'is_segment') and line.is_segment:
            if hasattr(line, 'segment_index') and hasattr(line, 'segment_total'):
                # Для последнего сегмента реплики - добавляем паузу
                if line.segment_index == line.segment_total - 1:
                    profile.pause_after += 200
                # Для НЕпервого сегмента - минимальная пауза перед
                elif line.segment_index > 0:
                    profile.pause_before += 50

        # Ограничение значений
        return self._clamp(profile)

    @staticmethod
    def _clamp(p: EmotionProfile) -> EmotionProfile:
        """Ограничение значений"""
        p.energy = max(0.5, min(p.energy, 1.5))
        p.tempo = max(0.7, min(p.tempo, 1.3))
        p.pitch = max(-0.5, min(p.pitch, 0.5))
        p.pause_before = min(p.pause_before, 1000)  # Макс 1 секунда
        p.pause_after = min(p.pause_after, 1000)
        return p