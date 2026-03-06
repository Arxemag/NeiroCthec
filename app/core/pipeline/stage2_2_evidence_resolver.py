# core/pipeline/stage2_2_evidence_resolver.py
"""
Stage 2.2 — Резолвер доказательств с взвешенным голосованием.
Принимает список Evidence и возвращает финальное решение о поле спикера.
"""
from typing import List
from dataclasses import dataclass, field

try:
    from .stage2_1_evidence_collectors import Evidence
except ImportError:
    from stage2_1_evidence_collectors import Evidence


@dataclass
class ResolverResult:
    """Результат работы резолвера"""
    speaker: str  # 'male', 'female', 'unknown'
    confidence: float  # 0.0 - 1.0
    used_evidences: List[Evidence] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)


class EvidenceResolver:
    """
    Резолвер доказательств с системой весов.
    Использует взвешенное голосование для определения пола.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        high_confidence_threshold: float = 0.6
    ):
        self.confidence_threshold = confidence_threshold
        self.high_confidence_threshold = high_confidence_threshold

    def resolve(self, evidences: List[Evidence]) -> ResolverResult:
        """
        Резолвит список доказательств в финальное решение.
        """
        if not evidences:
            return ResolverResult(
                speaker='unknown',
                confidence=0.0,
                reasoning=['Нет доказательств']
            )

        # Считаем взвешенные суммы для каждого пола
        scores = {'male': 0.0, 'female': 0.0}
        used_evidences = []

        for ev in evidences:
            if ev.gender in scores:
                scores[ev.gender] += ev.weight
                used_evidences.append(ev)

        total = scores['male'] + scores['female']

        if total == 0:
            return ResolverResult(
                speaker='unknown',
                confidence=0.0,
                used_evidences=used_evidences,
                reasoning=['Нет релевантных доказательств']
            )

        # Определяем победителя
        if scores['male'] > scores['female']:
            speaker = 'male'
            confidence = (scores['male'] - scores['female']) / total
        elif scores['female'] > scores['male']:
            speaker = 'female'
            confidence = (scores['female'] - scores['male']) / total
        else:
            speaker = 'unknown'
            confidence = 0.0

        # Проверяем на высокую уверенность (приоритетные сигналы)
        high_confidence_evidences = [
            ev for ev in evidences
            if ev.source == 'explicit_pronoun_verb' and ev.weight >= 2.5
        ]

        if high_confidence_evidences:
            # Если есть явная конструкция "глагол + я", доверяем ей полностью
            primary_ev = high_confidence_evidences[0]
            return ResolverResult(
                speaker=primary_ev.gender,
                confidence=0.95,
                used_evidences=high_confidence_evidences,
                reasoning=[f'Приоритет: {primary_ev.details}']
            )

        # Формируем reasoning
        reasoning = []
        reasoning.append(f"Счёт: male={scores['male']:.2f}, female={scores['female']:.2f}")

        if speaker != 'unknown':
            reasoning.append(f"Решение: {speaker} (confidence={confidence:.2f})")
        else:
            reasoning.append("Ничья, решение unknown")

        return ResolverResult(
            speaker=speaker,
            confidence=confidence,
            used_evidences=used_evidences,
            reasoning=reasoning
        )

    def is_confident(self, result: ResolverResult) -> bool:
        """Проверяет, достаточно ли уверенности для решения"""
        return result.confidence >= self.confidence_threshold

    def is_highly_confident(self, result: ResolverResult) -> bool:
        """Проверяет, очень ли высокая уверенность"""
        return result.confidence >= self.high_confidence_threshold
