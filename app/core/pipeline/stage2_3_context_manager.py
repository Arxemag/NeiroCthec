# core/pipeline/stage2_3_context_manager.py
"""
Stage 2.3 — Менеджер контекста для отслеживания диалогов.
Хранит информацию о предыдущих спикерах, сегментах и чередовании.
"""
from typing import Optional, Dict, List
from collections import deque
from dataclasses import dataclass, field


@dataclass
class DialogueContext:
    """Контекст текущего диалога"""
    last_speakers: deque = field(default_factory=lambda: deque(maxlen=10))
    segment_speakers: Dict[int, str] = field(default_factory=dict)
    dialogue_count: int = 0
    narrator_count: int = 0


class ContextManager:
    """
    Менеджер контекста для Stage 2.
    Отслеживает чередование спикеров, кэширует решения для сегментов.
    """

    def __init__(self, alternation_weight: float = 0.8):
        self.context = DialogueContext()
        self.alternation_weight = alternation_weight
        self._current_chapter: Optional[int] = None

    def get_segment_speaker(self, line) -> Optional[str]:
        """
        Возвращает закэшированного спикера для сегмента.
        Если line является сегментом и base_line_id уже обработан — возвращает speaker.
        """
        if not hasattr(line, 'is_segment') or not line.is_segment:
            return None

        base_id = getattr(line, 'base_line_id', None)
        if base_id is None:
            return None

        return self.context.segment_speakers.get(base_id)

    def set_segment_speaker(self, line, speaker: str):
        """Сохраняет спикера для сегмента"""
        if not hasattr(line, 'is_segment') or not line.is_segment:
            return

        base_id = getattr(line, 'base_line_id', None)
        if base_id is not None:
            self.context.segment_speakers[base_id] = speaker

    def update_dialogue_sequence(self, speaker: str):
        """Обновляет последовательность диалога"""
        if speaker != 'narrator':
            self.context.last_speakers.append(speaker)
            self.context.dialogue_count += 1
        else:
            self.context.narrator_count += 1

    def get_expected_speaker_by_alternation(self) -> Optional[str]:
        """
        Возвращает ожидаемого спикера на основе чередования.
        Если предыдущий был male → ожидаем female, и наоборот.
        """
        if not self.context.last_speakers:
            return None

        last = self.context.last_speakers[-1]
        if last == 'male':
            return 'female'
        elif last == 'female':
            return 'male'
        return None

    def get_last_speaker(self) -> Optional[str]:
        """Возвращает последнего спикера диалога"""
        if not self.context.last_speakers:
            return None
        return self.context.last_speakers[-1]

    def get_dominant_speaker(self) -> Optional[str]:
        """Возвращает доминирующего спикера в текущем контексте"""
        if not self.context.last_speakers:
            return None

        male_count = sum(1 for s in self.context.last_speakers if s == 'male')
        female_count = sum(1 for s in self.context.last_speakers if s == 'female')

        if male_count > female_count:
            return 'male'
        elif female_count > male_count:
            return 'female'
        return None

    def get_alternation_score(self, proposed_speaker: str) -> float:
        """
        Возвращает score для предложенного спикера на основе чередования.
        Высокий score если чередование соблюдается.
        """
        expected = self.get_expected_speaker_by_alternation()
        if expected is None:
            return 0.0

        if proposed_speaker == expected:
            return self.alternation_weight
        else:
            return -self.alternation_weight * 0.5

    def reset_chapter(self, chapter_id: int):
        """Сбрасывает контекст при смене главы"""
        self._current_chapter = chapter_id
        self.context.last_speakers.clear()
        self.context.segment_speakers.clear()

    def get_stats(self) -> Dict:
        """Возвращает статистику контекста"""
        return {
            'dialogue_count': self.context.dialogue_count,
            'narrator_count': self.context.narrator_count,
            'cached_segments': len(self.context.segment_speakers),
            'last_speakers': list(self.context.last_speakers),
        }
