# core/pipeline/stage2_4_fallback_strategies.py
"""
Stage 2.4 — Стратегии фолбэка для случаев, когда основной анализ не дал результата.
Используют контекст, статистику книги и эвристики.
"""
import re
from typing import Optional, Tuple, Dict

try:
    from .stage2_3_context_manager import ContextManager
except ImportError:
    ContextManager = None


class ContextAwareFallback:
    """
    Умный фолбэк с учётом контекста.
    Использует чередование, статистику книги и эвристики.
    """

    def __init__(self, use_narrator_fallback: bool = False):
        self.use_narrator_fallback = use_narrator_fallback

    def get_fallback_speaker(
        self,
        line,
        context_manager: Optional['ContextManager'],
        doc_stats: Optional[Dict] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Возвращает (speaker, reason) или None если фолбэк не сработал.
        """
        # 1. Пробуем чередование
        if context_manager:
            expected = context_manager.get_expected_speaker_by_alternation()
            if expected:
                return (expected, "чередование диалога")

        # 2. Пробуем статистику книги
        if doc_stats:
            male_ratio = doc_stats.get('male_ratio', 0.5)
            female_ratio = doc_stats.get('female_ratio', 0.5)

            if male_ratio > 0.7:
                return ('male', f"статистика книги (male={male_ratio:.0%})")
            elif female_ratio > 0.7:
                return ('female', f"статистика книги (female={female_ratio:.0%})")

        # 3. Последний спикер
        if context_manager:
            last = context_manager.get_last_speaker()
            if last and last != 'narrator':
                opposite = 'female' if last == 'male' else 'male'
                return (opposite, f"противоположность последнему ({last})")

        # 4. Анализ окончаний глаголов в тексте
        text = line.original.lower() if hasattr(line, 'original') else str(line).lower()
        verb_result = self._analyze_verb_endings(text)
        if verb_result:
            return verb_result

        # 5. Фолбэк по умолчанию
        if self.use_narrator_fallback:
            return ('narrator', "умолчание (narrator)")
        else:
            return ('male', "умолчание (male)")

    def _analyze_verb_endings(self, text: str) -> Optional[Tuple[str, str]]:
        """Анализирует окончания глаголов для фолбэка"""
        male_verbs = len(re.findall(r'\b\S+л\b', text))
        female_verbs = len(re.findall(r'\b\S+ла\b', text))

        if male_verbs > female_verbs:
            return ('male', f"глаголы м.р. ({male_verbs} vs {female_verbs})")
        elif female_verbs > male_verbs:
            return ('female', f"глаголы ж.р. ({female_verbs} vs {male_verbs})")

        return None


class StatisticalFallback:
    """
    Фолбэк на основе статистики книги.
    Использует накопленную информацию о распределении полов.
    """

    def __init__(self):
        self.male_count = 0
        self.female_count = 0

    def update_stats(self, speaker: str):
        """Обновляет статистику"""
        if speaker == 'male':
            self.male_count += 1
        elif speaker == 'female':
            self.female_count += 1

    def get_dominant_gender(self) -> str:
        """Возвращает доминирующий пол"""
        if self.male_count > self.female_count:
            return 'male'
        elif self.female_count > self.male_count:
            return 'female'
        return 'male'  # Default

    def get_ratio(self) -> Dict[str, float]:
        """Возвращает соотношение полов"""
        total = max(self.male_count + self.female_count, 1)
        return {
            'male_ratio': self.male_count / total,
            'female_ratio': self.female_count / total,
        }


class AlternationFallback:
    """
    Фолбэк на основе чередования.
    Если в диалоге чётное количество реплик — ожидаем того же спикера,
    нечётное — противоположного.
    """

    def __init__(self):
        self.current_sequence = []

    def update(self, speaker: str):
        """Обновляет последовательность"""
        self.current_sequence.append(speaker)
        if len(self.current_sequence) > 20:
            self.current_sequence = self.current_sequence[-20:]

    def get_expected(self) -> Optional[str]:
        """Возвращает ожидаемого спикера"""
        if not self.current_sequence:
            return None

        last = self.current_sequence[-1]
        if last == 'male':
            return 'female'
        elif last == 'female':
            return 'male'
        return None

    def reset(self):
        """Сбрасывает последовательность (при смене сцены/главы)"""
        self.current_sequence = []
