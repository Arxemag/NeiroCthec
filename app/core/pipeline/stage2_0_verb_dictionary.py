# core/pipeline/stage2_0_verb_dictionary.py
import re
from typing import Dict, Set, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

# 🔥 СПЕЦИАЛЬНЫЕ ГЛАГОЛЫ И КОНТЕКСТНЫЕ УКАЗАТЕЛИ
SPECIAL_VERBS = {
    'прошелестел': 'male', 'прошелестела': 'female',
    'прошептал': 'male', 'прошептала': 'female',
    'прозвучал': 'male', 'прозвучала': 'female',
    'послышался': 'male', 'послышалась': 'female',
    'раздался': 'male', 'раздалась': 'female'
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
    male_verbs: Set[str]
    female_verbs: Set[str]
    verb_base_forms: Dict[str, str]
    context_indicators: Dict[str, Set[str]]  # 🔥 ДОБАВЛЯЕМ КОНТЕКСТНЫЕ УКАЗАТЕЛИ

    def __init__(self):
        self.male_verbs = set()
        self.female_verbs = set()
        self.verb_base_forms = {}
        self.context_indicators = {'male': set(), 'female': set()}  # 🔥 ИНИЦИАЛИЗИРУЕМ

    def add_verb(self, verb: str, gender: str):
        """Добавляет глагол и автоматически генерирует противоположную форму"""
        # 🔥 ПРОВЕРЯЕМ СПЕЦИАЛЬНЫЕ ГЛАГОЛЫ
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
        # 🔥 РАСШИРЕННЫЙ СПИСОК ОКОНЧАНИЙ ДЛЯ ГЛАГОЛОВ
        endings = [
            'лась', 'алась', 'елась',  # возвратные формы ж.р.
            'лся', 'елся',  # возвратные формы м.р.
            'ла', 'ала', 'ела',  # обычные формы ж.р.
            'л', 'ел'  # обычные формы м.р.
        ]

        # Сортируем по длине (от самых длинных к коротким)
        endings.sort(key=len, reverse=True)

        for ending in endings:
            if verb.endswith(ending):
                return verb[:-len(ending)]

        return verb

    def _generate_opposite_form(self, verb: str, target_gender: str) -> str:
        """Генерирует противоположную родовую форму глагола"""
        base = self._get_base_form(verb)

        if target_gender == 'male':
            if verb.endswith(('лась', 'алась', 'елась')):  # Возвратные глаголы
                return base + 'лся'
            elif verb.endswith(('ла', 'ала', 'ела')):
                return base + 'л'
            elif verb.endswith('елась'):
                return base + 'елся'

        elif target_gender == 'female':
            if verb.endswith(('лся', 'елся')):  # Возвратные глаголы
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
            'male_indicators': len(self.context_indicators['male']),  # 🔥 ДОБАВЛЯЕМ
            'female_indicators': len(self.context_indicators['female'])
        }


class BookVerbAnalyzer:
    """
    Stage 2.0 - Анализатор глаголов и контекста книги
    """

    def __init__(self):
        # 🔥 ИСПРАВЛЕННЫЙ ПАТТЕРН ДЛЯ ГЛАГОЛОВ (включает "окрысилась")
        self.verb_pattern = re.compile(
            r'\b[а-я]+(лся|лась|елся|алась|ала?|ел[аи]?)(сь)?\b',
            re.IGNORECASE
        )
        self.context_pattern = re.compile(
            r'\b(господин|госпожа|мужчина|женщина|парень|девушка|он|она|ему|ей)\b',
            re.IGNORECASE
        )
        self.dictionary = VerbDictionary()
        self.analysis_stats = defaultdict(int)

    def analyze_book(self, lines: List['Line']) -> VerbDictionary:
        """Анализирует всю книгу и возвращает словарь"""
        print("🔍 Stage 2.0 - Анализ глаголов и контекста книги...")

        for i, line in enumerate(lines):
            if line.type != "dialogue":
                continue

            self._analyze_line(line.original, i)

        self._print_analysis_report()
        return self.dictionary

    def _analyze_line(self, text: str, line_num: int):
        """Анализирует одну строку на глаголы и контекст"""
        # 🔥 1. АНАЛИЗ ГЛАГОЛОВ
        matches = list(self.verb_pattern.finditer(text))

        for match in matches:
            verb = match.group(0).lower()

            # 🔥 УЛУЧШЕННОЕ ОПРЕДЕЛЕНИЕ РОДА
            if verb.endswith(('лся', 'елся', 'лся', 'ел')):  # мужской род
                self.dictionary.add_verb(verb, 'male')
                self.analysis_stats['male_verbs'] += 1
            elif verb.endswith(('ла', 'ала', 'алась', 'ела', 'лась', 'елась')):  # женский род
                self.dictionary.add_verb(verb, 'female')
                self.analysis_stats['female_verbs'] += 1

        # 🔥 2. АНАЛИЗ КОНТЕКСТНЫХ УКАЗАТЕЛЕЙ
        context_matches = list(self.context_pattern.finditer(text))
        for match in context_matches:
            word = match.group(0).lower()
            gender = self._determine_gender_from_context(word)
            if gender:
                self.dictionary.add_context_indicator(word, gender)
                self.analysis_stats[f'{gender}_indicators'] += 1

    def _determine_gender_from_context(self, word: str) -> str:
        """Определяет пол по контекстному слову"""
        male_words = ['господин', 'мужчина', 'парень', 'он', 'ему']
        female_words = ['госпожа', 'женщина', 'девушка', 'она', 'ей']

        if word in male_words:
            return 'male'
        elif word in female_words:
            return 'female'
        return None

    def _print_analysis_report(self):
        """Печатает отчет анализа"""
        stats = self.dictionary.get_stats()
        print(f"📊 Словарь создан:")
        print(f"   Глаголов м.р.: {stats['male_verbs']}")
        print(f"   Глаголов ж.р.: {stats['female_verbs']}")
        print(f"   Указателей м.р.: {stats['male_indicators']}")
        print(f"   Указателей ж.р.: {stats['female_indicators']}")
        print(f"   Базовых форм: {stats['base_forms']}")

        # Показываем примеры
        if self.dictionary.male_verbs:
            print(f"   Примеры глаголов м.р.: {list(self.dictionary.male_verbs)[:3]}")
        if self.dictionary.female_verbs:
            print(f"   Примеры глаголов ж.р.: {list(self.dictionary.female_verbs)[:3]}")
        if self.dictionary.context_indicators['male']:
            print(f"   Примеры указателей м.р.: {list(self.dictionary.context_indicators['male'])[:3]}")
        if self.dictionary.context_indicators['female']:
            print(f"   Примеры указателей ж.р.: {list(self.dictionary.context_indicators['female'])[:3]}")


# 🔥 ФУНКЦИЯ ДЛЯ АНАЛИЗА КОНТЕКСТА
def analyze_context(text: str, dictionary: VerbDictionary) -> Tuple[str, List[str]]:
    """Анализирует контекстные указатели в тексте"""
    reasoning = []

    male_score = 0
    female_score = 0

    # Проверяем контекстные указатели из словаря
    for indicator in dictionary.context_indicators['male']:
        if re.search(rf'\b{indicator}\b', text, re.IGNORECASE):
            male_score += 1
            reasoning.append(f"Мужской указатель: '{indicator}'")

    for indicator in dictionary.context_indicators['female']:
        if re.search(rf'\b{indicator}\b', text, re.IGNORECASE):
            female_score += 1
            reasoning.append(f"Женский указатель: '{indicator}'")

    # Проверяем глобальные контекстные паттерны
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
GLOBAL_VERB_DICTIONARY = VerbDictionary()


def get_global_verb_dictionary() -> VerbDictionary:
    return GLOBAL_VERB_DICTIONARY


def update_global_dictionary(new_verbs: VerbDictionary):
    GLOBAL_VERB_DICTIONARY.male_verbs.update(new_verbs.male_verbs)
    GLOBAL_VERB_DICTIONARY.female_verbs.update(new_verbs.female_verbs)
    GLOBAL_VERB_DICTIONARY.verb_base_forms.update(new_verbs.verb_base_forms)
    GLOBAL_VERB_DICTIONARY.context_indicators['male'].update(new_verbs.context_indicators['male'])
    GLOBAL_VERB_DICTIONARY.context_indicators['female'].update(new_verbs.context_indicators['female'])
