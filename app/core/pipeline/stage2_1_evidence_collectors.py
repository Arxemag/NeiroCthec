# core/pipeline/stage2_1_evidence_collectors.py
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict
import re
from dataclasses import dataclass
from core.models import Line


@dataclass
class Evidence:
    gender: str
    weight: float
    source: str
    details: str = ""


class EvidenceCollector(ABC):
    @abstractmethod
    def collect(self, line: Line) -> List[Evidence]:
        pass


class PatternEvidenceCollector(EvidenceCollector):
    def __init__(self, patterns: Dict[str, Tuple[str, float]]):
        self.patterns = patterns

    def collect(self, line: Line) -> List[Evidence]:
        evidences = []
        text = self._prepare_text(line)

        for pattern, (gender, weight) in self.patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                evidences.append(Evidence(
                    gender=gender,
                    weight=weight,
                    source="pattern",
                    details=f"pattern: {pattern}"
                ))
        return evidences

    def _prepare_text(self, line: Line) -> str:
        text = line.original.lower()
        if line.remarks:
            for remark in line.remarks:
                text += " " + remark.text.lower()
        return text


class PronounEvidenceCollector(EvidenceCollector):
    def __init__(self, weights: Dict[str, float]):
        self.weights = weights

    def collect(self, line: Line) -> List[Evidence]:
        text = line.original.lower()
        if line.remarks:
            for remark in line.remarks:
                text += " " + remark.text.lower()

        male_pronouns = len(re.findall(r'\bон[ауе]?\b', text))
        female_pronouns = len(re.findall(r'\bона\b', text))

        evidences = []
        if male_pronouns > 0 or female_pronouns > 0:
            total = male_pronouns + female_pronouns
            if male_pronouns > female_pronouns:
                ratio = male_pronouns / total
                evidences.append(Evidence(
                    gender="male",
                    weight=ratio * self.weights['pronoun_ratio'],
                    source="pronouns",
                    details=f"male:{male_pronouns}, female:{female_pronouns}"
                ))
            elif female_pronouns > male_pronouns:
                ratio = female_pronouns / total
                evidences.append(Evidence(
                    gender="female",
                    weight=ratio * self.weights['pronoun_ratio'],
                    source="pronouns",
                    details=f"male:{male_pronouns}, female:{female_pronouns}"
                ))
        return evidences


class NameEvidenceCollector(EvidenceCollector):
    def __init__(self, female_names: set, male_names: set, weight: float):
        self.female_names = female_names
        self.male_names = male_names
        self.weight = weight

    def collect(self, line: Line) -> List[Evidence]:
        text = line.original.lower()
        evidences = []

        for name in self.female_names:
            if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                evidences.append(Evidence(
                    gender="female",
                    weight=self.weight,
                    source="name",
                    details=f"name: {name}"
                ))

        for name in self.male_names:
            if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                evidences.append(Evidence(
                    gender="male",
                    weight=self.weight,
                    source="name",
                    details=f"name: {name}"
                ))

        return evidences
