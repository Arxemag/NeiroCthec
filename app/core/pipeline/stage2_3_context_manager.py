# core/pipeline/stage2_3_context_manager.py
from typing import Dict, Optional, List  # 🔥 ДОБАВЛЯЕМ ИМПОРТ
from dataclasses import dataclass, field
from core.models import Line


@dataclass
class DialogueContext:
    last_speaker: Optional[str] = None
    speaker_sequence: List[str] = field(default_factory=list)  # 🔥 ИСПРАВЛЯЕМ
    segment_speakers: Dict[int, str] = field(default_factory=dict)  # 🔥 ИСПРАВЛЯЕМ

    # Убираем __post_init__ так как используем field(default_factory)


class ContextManager:
    def __init__(self):
        self.context = DialogueContext()

    def get_segment_speaker(self, line: Line) -> Optional[str]:
        """Получает спикера для сегмента из контекста"""
        if line.is_segment and line.base_line_id is not None:
            return self.context.segment_speakers.get(line.base_line_id)
        return None

    def set_segment_speaker(self, line: Line, speaker: str):
        """Сохраняет спикера для сегмента в контекст"""
        if line.is_segment and line.base_line_id is not None:
            self.context.segment_speakers[line.base_line_id] = speaker

    def update_dialogue_sequence(self, speaker: str):
        """Обновляет последовательность диалога"""
        if speaker != "narrator" and speaker != "unknown":
            self.context.last_speaker = speaker
            self.context.speaker_sequence.append(speaker)

            # Ограничиваем длину последовательности
            if len(self.context.speaker_sequence) > 10:
                self.context.speaker_sequence.pop(0)

    def get_last_speaker(self) -> Optional[str]:
        """Получает последнего спикера в диалоге"""
        return self.context.last_speaker

    def get_speaker_alternation(self) -> float:
        """Возвращает коэффициент чередования спикеров (для анализа паттернов)"""
        if len(self.context.speaker_sequence) < 2:
            return 0.5

        alternations = 0
        for i in range(1, len(self.context.speaker_sequence)):
            if self.context.speaker_sequence[i] != self.context.speaker_sequence[i - 1]:
                alternations += 1

        return alternations / (len(self.context.speaker_sequence) - 1)
