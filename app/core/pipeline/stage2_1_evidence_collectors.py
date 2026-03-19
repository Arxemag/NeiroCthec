# core/pipeline/stage2_1_evidence_collectors.py
"""
Stage 2.1 — Коллекторы доказательств для определения пола спикера.
Каждый коллектор собирает доказательства определённого типа.
"""
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class Evidence:
    """Единица доказательства"""
    gender: str  # 'male', 'female', 'unknown'
    weight: float  # Вес доказательства (0.0 - 1.0)
    source: str  # Источник: 'pattern', 'pronoun', 'name', 'verb', etc.
    details: str  # Детали для дебага


class BaseEvidenceCollector:
    """Базовый класс для коллекторов доказательств"""

    def collect(self, line) -> List[Evidence]:
        raise NotImplementedError


class PatternEvidenceCollector(BaseEvidenceCollector):
    """Коллектор на основе regex-паттернов"""

    def __init__(self, pattern_map: Dict[str, Tuple[str, float]] = None):
        self.pattern_map = pattern_map or {
            r"\b(сказал|ответил|спросил|произнёс|произнес|доложил|прошептал|крикнул)\b": ("male", 1.0),
            r"\b(сказала|ответила|спросила|произнесла|доложила|прошептала|крикнула)\b": ("female", 1.0),
            r"\b(мужчина|парень|юноша|господин)\b": ("male", 0.8),
            r"\b(женщина|девушка|госпожа|леди)\b": ("female", 0.8),
        }
        self._compiled = {re.compile(p, re.IGNORECASE): v for p, v in self.pattern_map.items()}

    def collect(self, line) -> List[Evidence]:
        evidences = []
        text = line.original.lower() if hasattr(line, 'original') else str(line).lower()

        for pattern, (gender, weight) in self._compiled.items():
            matches = pattern.findall(text)
            for match in matches:
                evidences.append(Evidence(
                    gender=gender,
                    weight=weight,
                    source='pattern',
                    details=f"Паттерн '{match}'"
                ))

        return evidences


class PronounEvidenceCollector(BaseEvidenceCollector):
    """Коллектор на основе местоимений"""

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {'pronoun_ratio': 1.2}
        self.male_pronouns = re.compile(r'\bон[ауе]?\b', re.IGNORECASE)
        self.female_pronouns = re.compile(r'\bона\b', re.IGNORECASE)

    def collect(self, line) -> List[Evidence]:
        evidences = []
        text = line.original.lower() if hasattr(line, 'original') else str(line).lower()

        male_count = len(self.male_pronouns.findall(text))
        female_count = len(self.female_pronouns.findall(text))

        weight = self.weights.get('pronoun_ratio', 1.0)

        if male_count > female_count * 2:
            evidences.append(Evidence(
                gender='male',
                weight=weight * 0.8,
                source='pronoun',
                details=f"Местоимения м.р.: {male_count} vs ж.р.: {female_count}"
            ))
        elif female_count > male_count * 2:
            evidences.append(Evidence(
                gender='female',
                weight=weight * 0.8,
                source='pronoun',
                details=f"Местоимения ж.р.: {female_count} vs м.р.: {male_count}"
            ))

        return evidences


class NameEvidenceCollector(BaseEvidenceCollector):
    """Коллектор на основе имён"""

    def __init__(self, female_names: set = None, male_names: set = None, weight: float = 1.0):
        self.weight = weight
        self.female_names = female_names or {
            "анна", "мария", "екатерина", "ольга", "дина", "наталья", "елена",
            "светлана", "ирина", "юлия", "татьяна", "людмила", "лора", "девушка",
            "александра", "виктория", "дарья", "ксения", "анастасия", "полина",
            "марина", "галина", "валентина", "лариса", "оксана", "надежда",
            "любовь", "тамара", "вера", "зинаида", "валерия", "кристина",
            "алёна", "жанна", "инна", "софия", "диана", "агата", "варвара"
        }
        self.male_names = male_names or {
            "иван", "пётр", "сергей", "алексей", "василий", "андрей", "дмитрий",
            "михаил", "владимир", "николай", "александр", "евгений", "павел",
            "виктор", "олег", "юрий", "игорь", "анатолий", "валерий", "борис",
            "геннадий", "степан", "константин", "леонид", "валентин", "роман",
            "аркадий", "григорий", "фёдор", "ярослав", "максим", "артём",
            "илья", "егор", "даниил", "кирилл", "станислав", "богдан", "тимур"
        }

    def collect(self, line) -> List[Evidence]:
        evidences = []
        text = line.original.lower() if hasattr(line, 'original') else str(line).lower()

        for name in self.female_names:
            if re.search(rf'\b{re.escape(name)}\b', text):
                evidences.append(Evidence(
                    gender='female',
                    weight=self.weight,
                    source='name',
                    details=f"Женское имя: '{name}'"
                ))

        for name in self.male_names:
            if re.search(rf'\b{re.escape(name)}\b', text):
                evidences.append(Evidence(
                    gender='male',
                    weight=self.weight,
                    source='name',
                    details=f"Мужское имя: '{name}'"
                ))

        return evidences


class VerbEndingEvidenceCollector(BaseEvidenceCollector):
    """Коллектор на основе окончаний глаголов"""

    def __init__(self, weight: float = 2.5):
        self.weight = weight
        self.male_patterns = [r'\b\S+л\b', r'\b\S+лся\b']
        self.female_patterns = [r'\b\S+ла\b', r'\b\S+лась\b']

    def collect(self, line) -> List[Evidence]:
        evidences = []
        text = line.original.lower() if hasattr(line, 'original') else str(line).lower()

        male_count = sum(len(re.findall(p, text)) for p in self.male_patterns)
        female_count = sum(len(re.findall(p, text)) for p in self.female_patterns)

        if male_count > 0:
            evidences.append(Evidence(
                gender='male',
                weight=self.weight * (male_count / max(male_count + female_count, 1)),
                source='verb_ending',
                details=f"Глаголы м.р.: {male_count}"
            ))

        if female_count > 0:
            evidences.append(Evidence(
                gender='female',
                weight=self.weight * (female_count / max(male_count + female_count, 1)),
                source='verb_ending',
                details=f"Глаголы ж.р.: {female_count}"
            ))

        return evidences


class ExplicitPronounVerbCollector(BaseEvidenceCollector):
    """Коллектор для явных конструкций 'глагол + я' (самый сильный сигнал)"""

    def __init__(self, weight: float = 3.0):
        self.weight = weight
        self.patterns = [
            (r'(\S+л)[,–—-]*\s+я\b', 'male'),
            (r'(\S+ла)[,–—-]*\s+я\b', 'female'),
            (r'\bя\s+(\S+л)\b', 'male'),
            (r'\bя\s+(\S+ла)\b', 'female'),
            (r'\bя\s+(\S+лся)\b', 'male'),
            (r'\bя\s+(\S+лась)\b', 'female'),
        ]

    def collect(self, line) -> List[Evidence]:
        evidences = []
        text = line.original.lower() if hasattr(line, 'original') else str(line).lower()

        if ' я' not in text and 'я ' not in text:
            return evidences

        for pattern, gender in self.patterns:
            matches = re.findall(pattern, text)
            for verb in matches:
                evidences.append(Evidence(
                    gender=gender,
                    weight=self.weight,
                    source='explicit_pronoun_verb',
                    details=f"Явная конструкция: '{verb} + я'"
                ))

        return evidences
