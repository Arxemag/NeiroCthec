# core/pipeline/stage2_4_fallback_strategies.py
from abc import ABC, abstractmethod
from typing import Dict  # 🔥 ДОБАВЛЯЕМ
from core.models import Line
from .stage2_3_context_manager import ContextManager


class FallbackStrategy(ABC):
    @abstractmethod
    def get_fallback_speaker(self, line: Line, context: ContextManager, document_stats: Dict) -> str:
        pass


class ContextAwareFallback(FallbackStrategy):
    def __init__(self, use_narrator_fallback: bool = False):
        self.use_narrator_fallback = use_narrator_fallback

    def get_fallback_speaker(self, line: Line, context: ContextManager, document_stats: Dict) -> str:
        # 1. Пробуем контекст диалога
        last_speaker = context.get_last_speaker()
        if last_speaker and last_speaker != "narrator":
            return last_speaker

        # 2. Анализ статистики документа
        if document_stats.get('male_ratio', 0.5) > 0.6:
            return "male"
        elif document_stats.get('female_ratio', 0.5) > 0.6:
            return "female"

        # 3. Фолбэк по умолчанию
        if self.use_narrator_fallback:
            return "narrator"
        else:
            return "male"


class AlternatingFallback(FallbackStrategy):
    """Чередует спикеров на основе паттернов диалога"""

    def get_fallback_speaker(self, line: Line, context: ContextManager, document_stats: Dict) -> str:
        alternation = context.get_speaker_alternation()
        last_speaker = context.get_last_speaker()

        # Если высокое чередование, пробуем противоположный пол
        if alternation > 0.7 and last_speaker:
            if last_speaker == "male":
                return "female"
            elif last_speaker == "female":
                return "male"

        # Иначе стандартная логика
        if last_speaker and last_speaker != "narrator":
            return last_speaker

        return "male" if document_stats.get('male_ratio', 0.5) > 0.4 else "female"
