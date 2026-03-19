# core/pipeline/stage2_0_verb_dictionary.py
"""
Stage 2.0 — Динамический словарь глаголов с автогенерацией форм.
Анализирует книгу и строит словарь специфичных глаголов для определения пола спикера.
"""
import re
from typing import Dict, Set, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

SPECIAL_VERBS = {
    'прошелестел': 'male', 'прошелестела': 'female',
    'прошептал': 'male', 'прошептала': 'female',
    'прозвучал': 'male', 'прозвучала': 'female',
    'послышался': 'male', 'послышалась': 'female',
    'раздался': 'male', 'раздалась': 'female',
}

CONTEXT_INDICATORS = {
    'male': [
        r'господин', r'мужчин', r'парень', r'юноша', r'отец', r'брат',
        r'он\s+', r'ему\s+', r'им\s+', r'у него', r'сэр', r'господ'
    ],
    'female': [
        r'госпожа', r'женщин', r'девушк', r'девочк', r'мать', r'сестра',
        r'она\s+', r'ей\s+', r'у неё', r'леди', r'мадемуазель'
    ]
}


@dataclass
class VerbDictionary:
    """Динамический словарь глаголов с автодополнением форм"""
    male_verbs: Set[str] = field(default_factory=set)
    female_verbs: Set[str] = field(default_factory=set)
    verb_base_forms: Dict[str, str] = field(default_factory=dict)
    context_indicators: Dict[str, Set[str]] = field(default_factory=lambda: {'male': set(), 'female': set()})

    def add_verb(self, verb: str, gender: str):
        """Добавляет глагол и автоматически генерирует противоположную форму"""
        if verb in SPECIAL_VERBS:
            gender = SPECIAL_VERBS[verb]

        base_form = self._get_base_form(verb)

        if gender == 'male':
            self.male_verbs.add(verb)
            self.verb_base_forms[base_form] = 'male'
            female_form = self._generate_opposite_form(verb, 'female')
            if female_form:
                self.female_verbs.add(female_form)

        elif gender == 'female':
            self.female_verbs.add(verb)
            self.verb_base_forms[base_form] = 'female'
            male_form = self._generate_opposite_form(verb, 'male')
            if male_form:
                self.male_verbs.add(male_form)

    def add_context_indicator(self, word: str, gender: str):
        """Добавляет контекстный указатель"""
        if gender in ['male', 'female']:
            self.context_indicators[gender].add(word.lower())

    def _get_base_form(self, verb: str) -> str:
        """Извлекает базовую форму глагола"""
        endings = [
            'лась', 'алась', 'елась',
            'лся', 'елся',
            'ла', 'ала', 'ела',
            'л', 'ел'
        ]
        endings.sort(key=len, reverse=True)

        for ending in endings:
            if verb.endswith(ending):
                return verb[:-len(ending)]

        return verb

    def _generate_opposite_form(self, verb: str, target_gender: str) -> str | None:
        """Генерирует противоположную родовую форму глагола"""
        base = self._get_base_form(verb)

        if target_gender == 'male':
            if verb.endswith(('лась', 'алась', 'елась')):
                return base + 'лся'
            elif verb.endswith(('ла', 'ала', 'ела')):
                return base + 'л'
            elif verb.endswith('елась'):
                return base + 'елся'

        elif target_gender == 'female':
            if verb.endswith(('лся', 'елся')):
                return base + 'лась'
            elif verb.endswith(('л', 'ел')):
                return base + 'ла'
            elif verb.endswith('елся'):
                return base + 'елась'

        return None

    def get_stats(self) -> Dict:
        """Статистика словаря"""
        return {
            'male_verbs': len(self.male_verbs),
            'female_verbs': len(self.female_verbs),
            'base_forms': len(self.verb_base_forms),
            'male_indicators': len(self.context_indicators['male']),
            'female_indicators': len(self.context_indicators['female'])
        }


class BookVerbAnalyzer:
    """Stage 2.0 — Анализатор глаголов и контекста книги"""

    def __init__(self):
        self.verb_pattern = re.compile(
            r'\b[а-яё]+(лся|лась|елся|алась|ала?|ел[аи]?)(сь)?\b',
            re.IGNORECASE
        )
        self.context_pattern = re.compile(
            r'\b(господин|госпожа|мужчина|женщина|парень|девушка|он|она|ему|ей)\b',
            re.IGNORECASE
        )
        self.dictionary = VerbDictionary()
        self.analysis_stats = defaultdict(int)

    def analyze_book(self, lines: List) -> VerbDictionary:
        """Анализирует всю книгу и возвращает словарь"""
        for line in lines:
            if not hasattr(line, 'type') or line.type != "dialogue":
                continue
            self._analyze_line(line.original if hasattr(line, 'original') else str(line))

        return self.dictionary

    def _analyze_line(self, text: str):
        """Анализирует одну строку на глаголы и контекст"""
        matches = list(self.verb_pattern.finditer(text))

        for match in matches:
            verb = match.group(0).lower()

            if verb.endswith(('лся', 'елся', 'ел')):
                self.dictionary.add_verb(verb, 'male')
                self.analysis_stats['male_verbs'] += 1
            elif verb.endswith(('ла', 'ала', 'алась', 'ела', 'лась', 'елась')):
                self.dictionary.add_verb(verb, 'female')
                self.analysis_stats['female_verbs'] += 1

        context_matches = list(self.context_pattern.finditer(text))
        for match in context_matches:
            word = match.group(0).lower()
            gender = self._determine_gender_from_context(word)
            if gender:
                self.dictionary.add_context_indicator(word, gender)
                self.analysis_stats[f'{gender}_indicators'] += 1

    def _determine_gender_from_context(self, word: str) -> str | None:
        """Определяет пол по контекстному слову"""
        male_words = ['господин', 'мужчина', 'парень', 'он', 'ему']
        female_words = ['госпожа', 'женщина', 'девушка', 'она', 'ей']

        if word in male_words:
            return 'male'
        elif word in female_words:
            return 'female'
        return None


def analyze_context(text: str, dictionary: VerbDictionary) -> Tuple[str, List[str]]:
    """Анализирует контекстные указатели в тексте"""
    reasoning = []
    male_score = 0
    female_score = 0

    for indicator in dictionary.context_indicators['male']:
        if re.search(rf'\b{re.escape(indicator)}\b', text, re.IGNORECASE):
            male_score += 1
            reasoning.append(f"Мужской указатель: '{indicator}'")

    for indicator in dictionary.context_indicators['female']:
        if re.search(rf'\b{re.escape(indicator)}\b', text, re.IGNORECASE):
            female_score += 1
            reasoning.append(f"Женский указатель: '{indicator}'")

    for pattern in CONTEXT_INDICATORS['male']:
        if re.search(pattern, text, re.IGNORECASE):
            male_score += 1
            reasoning.append(f"Мужской паттерн: '{pattern}'")

    for pattern in CONTEXT_INDICATORS['female']:
        if re.search(pattern, text, re.IGNORECASE):
            female_score += 1
            reasoning.append(f"Женский паттерн: '{pattern}'")

    if male_score > female_score:
        return "male", reasoning
    elif female_score > male_score:
        return "female", reasoning
    else:
        return "unknown", reasoning


# Глобальный словарь
_GLOBAL_VERB_DICTIONARY = VerbDictionary()


def get_global_verb_dictionary() -> VerbDictionary:
    return _GLOBAL_VERB_DICTIONARY


def update_global_dictionary(new_verbs: VerbDictionary):
    _GLOBAL_VERB_DICTIONARY.male_verbs.update(new_verbs.male_verbs)
    _GLOBAL_VERB_DICTIONARY.female_verbs.update(new_verbs.female_verbs)
    _GLOBAL_VERB_DICTIONARY.verb_base_forms.update(new_verbs.verb_base_forms)
    _GLOBAL_VERB_DICTIONARY.context_indicators['male'].update(new_verbs.context_indicators['male'])
    _GLOBAL_VERB_DICTIONARY.context_indicators['female'].update(new_verbs.context_indicators['female'])
