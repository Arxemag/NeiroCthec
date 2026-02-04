# core/pipeline/stage2_2_evidence_resolver.py
from typing import List, Tuple, Dict  # 🔥 ДОБАВЛЯЕМ
from dataclasses import dataclass
from .stage2_1_evidence_collectors import Evidence

@dataclass
class ResolutionResult:
    speaker: str
    confidence: float
    used_evidences: List[Evidence]
    all_evidences: List[Evidence]


class EvidenceResolver:
    def __init__(self, confidence_threshold: float = 1.5, high_confidence_threshold: float = 2.0):
        self.confidence_threshold = confidence_threshold
        self.high_confidence_threshold = high_confidence_threshold

    def resolve(self, evidences: List[Evidence]) -> ResolutionResult:
        if not evidences:
            return ResolutionResult(
                speaker="unknown",
                confidence=0.0,
                used_evidences=[],
                all_evidences=evidences
            )

        # Группируем по полу
        scores = {}
        gender_evidences = {}

        for evidence in evidences:
            if evidence.gender not in scores:
                scores[evidence.gender] = 0.0
                gender_evidences[evidence.gender] = []

            scores[evidence.gender] += evidence.weight
            gender_evidences[evidence.gender].append(evidence)

        if not scores:
            return ResolutionResult(
                speaker="unknown",
                confidence=0.0,
                used_evidences=[],
                all_evidences=evidences
            )

        # Находим лучший результат
        best_gender = max(scores.keys(), key=lambda g: scores[g])
        best_score = scores[best_gender]

        # Определяем уровень уверенности
        confidence_level = "low"
        if best_score >= self.high_confidence_threshold:
            confidence_level = "high"
        elif best_score >= self.confidence_threshold:
            confidence_level = "medium"

        return ResolutionResult(
            speaker=best_gender if confidence_level != "low" else "unknown",
            confidence=best_score,
            used_evidences=gender_evidences.get(best_gender, []),
            all_evidences=evidences
        )
