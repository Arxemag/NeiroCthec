# core/pipeline/stage2_5_character_collector.py
import re
import json
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# Попробуем импортировать Natasha
try:
    from natasha import Doc, NewsMorphTagger, NewsEmbedding, Segmenter

    NATASHA_AVAILABLE = True
    print("✅ Natasha доступна для использования")
except ImportError:
    NATASHA_AVAILABLE = False
    print("⚠️  Natasha не установлена, будет использована базовая версия")


@dataclass
class CharacterMention:
    """Упоминание персонажа"""
    line_idx: int
    line_text: str
    context: str
    character_name: str
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)


@dataclass
class CharacterData:
    """Данные о персонаже"""
    name: str
    mentions: List[CharacterMention] = field(default_factory=list)
    first_occurrence: int = 0
    last_occurrence: int = 0

    @property
    def mention_count(self):
        return len(self.mentions)


class CharacterCollector:
    """
    Stage 2.6 - Коллекционер имен персонажей с использованием Natasha
    """

    def __init__(self):
        self.characters: Dict[str, CharacterData] = {}
        self.stats = {
            'total_characters': 0,
            'total_mentions': 0,
            'lines_processed': 0
        }

        # Инициализация Natasha, если доступна
        self.use_natasha = False
        if NATASHA_AVAILABLE:
            try:
                self.segmenter = Segmenter()
                self.emb = NewsEmbedding()
                self.morph_tagger = NewsMorphTagger(self.emb)
                self.use_natasha = True
                print("✅ Natasha инициализирована успешно")
            except Exception as e:
                print(f"⚠️  Ошибка инициализации Natasha: {e}")
                self.use_natasha = False

        # Известные имена для повышения уверенности
        self.known_first_names = self._load_known_first_names()

        # Глаголы речи
        self.speaking_verbs = {
            'сказал', 'ответил', 'спросил', 'воскликнул', 'прошептал',
            'произнес', 'закричал', 'пробормотал', 'выдохнул', 'произнёс',
            'возразил', 'добавил', 'продолжил', 'заявил', 'объявил',
            'сообщил', 'пояснил', 'заметил', 'подтвердил', 'крикнул',
            'проговорил', 'вздохнул', 'усмехнулся', 'улыбнулся', 'хмыкнул',
            'рассмеялся', 'прервал', 'перебил', 'вмешался', 'обратился'
        }

        # Конструкции обращения
        self.addressing_patterns = ['зовут', 'имя', 'по имени', 'называется']

    def _load_known_first_names(self) -> Set[str]:
        """Загружает известные имена"""
        return {
            # Женские имена
            'Мария', 'Анна', 'Елена', 'Ольга', 'Татьяна', 'Наталья',
            'Ирина', 'Светлана', 'Юлия', 'Екатерина', 'Александра',
            'Виктория', 'Дарья', 'Ксения', 'Анастасия', 'Полина',
            'Марина', 'Людмила', 'Галина', 'Валентина', 'Лариса',
            'Оксана', 'Надежда', 'Любовь', 'Тамара', 'Вера',
            'Зинаида', 'Валерия', 'Кристина', 'Алёна', 'Жанна',
            'Инна', 'София', 'Диана', 'Агата', 'Варвара', 'Агния',
            'Милена', 'Ульяна', 'Амина', 'Эвелина', 'Алина', 'Василиса',

            # Мужские имена
            'Александр', 'Сергей', 'Дмитрий', 'Андрей', 'Алексей',
            'Михаил', 'Иван', 'Николай', 'Владимир', 'Павел',
            'Виктор', 'Олег', 'Юрий', 'Игорь', 'Василий', 'Петр',
            'Анатолий', 'Валерий', 'Борис', 'Геннадий', 'Степан',
            'Константин', 'Леонид', 'Валентин', 'Роман', 'Аркадий',
            'Григорий', 'Фёдор', 'Ярослав', 'Максим', 'Артём',
            'Артемий', 'Илья', 'Егор', 'Даниил', 'Кирилл', 'Станислав',
            'Богдан', 'Тимур', 'Антон', 'Виталий', 'Георгий', 'Руслан'
        }

    def collect_characters(self, lines: List) -> Dict[str, CharacterData]:
        """
        Собирает имена персонажей из списка строк Line
        """
        print("🔍 Stage 2.6 - Сбор имен персонажей...")
        if self.use_natasha:
            print("🤖 Используется Natasha для морфологического анализа")
        else:
            print("🔤 Используется базовый анализ")

        self.stats['lines_processed'] = 0

        for i, line in enumerate(lines):
            if hasattr(line, 'type') and line.type in ["dialogue", "narrative"]:
                self._process_line(line.original, i)
                self.stats['lines_processed'] += 1

        self._calculate_confidence()
        self._filter_results()
        self._print_collection_report()
        return self.characters

    def _process_line(self, text: str, line_idx: int):
        """Обрабатывает одну строку текста"""
        if self.use_natasha:
            self._process_with_natasha(text, line_idx)
        else:
            self._process_basic(text, line_idx)

    def _process_with_natasha(self, text: str, line_idx: int):
        """Обработка с использованием Natasha"""
        try:
            doc = Doc(text)
            doc.segment()
            doc.tag_morph(self.morph_tagger)

            # Ищем имена собственные (PROPN - proper noun)
            for token in doc.tokens:
                if (token.pos == 'PROPN' and  # Имя собственное
                        token.text[0].isupper() and  # Начинается с заглавной
                        len(token.text) > 2):  # Достаточной длины

                    # Проверяем контекст на глаголы речи
                    confidence = 0.7
                    evidence = ['Имя собственное (PROPN)']

                    # Проверяем наличие глаголов речи рядом
                    if self._has_speaking_verb_near(text, token.text):
                        confidence = 0.9
                        evidence.append('Рядом с глаголом речи')

                    # Проверяем на известные имена
                    if token.text in self.known_first_names:
                        confidence += 0.1
                        evidence.append('Известное имя')

                    self._add_character_mention(token.text, text, line_idx, confidence, evidence)

        except Exception as e:
            print(f"⚠️  Ошибка обработки строки {line_idx} с Natasha: {e}")
            # fallback на базовый метод
            self._process_basic(text, line_idx)

    def _process_basic(self, text: str, line_idx: int):
        """Базовая обработка без Natasha"""
        # Ищем имена по глаголам речи
        for verb in self.speaking_verbs:
            # Паттерн: [глагол] [имя]
            pattern = rf'{verb}[^а-яА-Я]*\s+([А-Я][а-я]{{2,}}(?:\s+[А-Я][а-я]{{2,}}){{0,2}})'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                evidence = [f'Глагол речи "{verb}" перед именем']
                self._add_character_mention(name, text, line_idx, 0.8, evidence)

        # Паттерн: [имя], [глагол]
        pattern = rf'([А-Я][а-я]{{2,}}(?:\s+[А-Я][а-я]{{2,}}){{0,2}})\s*[,]\s*({"|".join(self.speaking_verbs)})'
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            name = match.group(1).strip()
            verb = match.group(2)
            evidence = [f'Обращение к персонажу, затем глагол речи "{verb}"']
            self._add_character_mention(name, text, line_idx, 0.7, evidence)

        # Конструкции обращения
        for addr_pattern in self.addressing_patterns:
            pattern = rf'{addr_pattern}[^а-яА-Я]*\s+([А-Я][а-я]{{2,}}(?:\s+[А-Я][а-я]{{2,}}){{0,2}})'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                evidence = [f'Конструкция обращения "{addr_pattern}"']
                self._add_character_mention(name, text, line_idx, 0.9, evidence)

    def _has_speaking_verb_near(self, text: str, name: str) -> bool:
        """Проверяет наличие глаголов речи рядом с именем"""
        for verb in self.speaking_verbs:
            if re.search(rf'{verb}[^а-яА-Я]*\s+{re.escape(name)}', text, re.IGNORECASE):
                return True
            if re.search(rf'{re.escape(name)}\s*[,]\s*{verb}', text, re.IGNORECASE):
                return True
        return False

    def _add_character_mention(self, name: str, text: str, line_idx: int, confidence: float, evidence: List[str]):
        """Добавляет упоминание персонажа"""
        # Базовая валидация
        if not self._is_valid_character_name(name):
            return

        # Создаем контекст
        context = self._extract_context(text, name)

        mention = CharacterMention(
            line_idx=line_idx,
            line_text=text,
            context=context,
            character_name=name,
            confidence=confidence,
            evidence=evidence
        )

        # Добавляем в базу данных
        if name not in self.characters:
            self.characters[name] = CharacterData(
                name=name,
                first_occurrence=line_idx,
                last_occurrence=line_idx
            )

        self.characters[name].mentions.append(mention)
        self.characters[name].last_occurrence = line_idx
        self.stats['total_mentions'] += 1

    def _is_valid_character_name(self, name: str) -> bool:
        """Проверяет, является ли имя допустимым именем персонажа"""
        if not name or len(name) < 2:
            return False

        # Не должно содержать системных терминов
        system_terms = {
            'система', 'задание', 'награда', 'карма', 'вселенная', 'мир',
            'порядок', 'хаос', 'время', 'пространство', 'энергия', 'силы',
            'точно', 'очень', 'много', 'мало', 'больше', 'меньше',
            'первый', 'второй', 'третий', 'четвертый', 'пятый'
        }
        name_lower = name.lower()
        if any(term in name_lower for term in system_terms):
            return False

        # Не должно быть глаголом или прилагательным
        action_words = {
            'говорил', 'думал', 'знал', 'понимал', 'видел', 'слышал',
            'работал', 'жил', 'думал', 'сказал', 'ответил', 'спросил',
            'воскликнул', 'прошептал', 'произнес', 'закричал'
        }
        if name_lower in action_words:
            return False

        # Не должно содержать только цифры
        if name.replace(' ', '').isdigit():
            return False

        return True

    def _calculate_confidence(self):
        """Пересчитывает уверенность на основе множественных факторов"""
        for name, char_data in self.characters.items():
            if not char_data.mentions:
                continue

            # Базовая уверенность первого упоминания
            base_confidence = max(mention.confidence for mention in char_data.mentions)

            # Бонус за количество упоминаний
            mention_bonus = min((char_data.mention_count - 1) * 0.1, 0.3)

            # Бонус за разные типы доказательств
            evidence_types = set()
            for mention in char_data.mentions:
                evidence_types.update(mention.evidence)
            evidence_bonus = min(len(evidence_types) * 0.05, 0.2)

            final_confidence = min(base_confidence + mention_bonus + evidence_bonus, 1.0)

            # Обновляем уверенность во всех упоминаниях
            for mention in char_data.mentions:
                mention.confidence = final_confidence

    def _filter_results(self):
        """Фильтрует результаты по финальной уверенности"""
        to_remove = []
        for name, char_data in list(self.characters.items()):
            # Требования: минимум 2 упоминания и уверенность > 0.6
            if (char_data.mention_count < 2 or
                    not char_data.mentions or
                    char_data.mentions[0].confidence < 0.6):
                to_remove.append(name)

        for name in to_remove:
            if name in self.characters:
                self.stats['total_mentions'] -= len(self.characters[name].mentions)
                del self.characters[name]

        self.stats['total_characters'] = len(self.characters)

    def _extract_context(self, text: str, name: str, context_size: int = 80) -> str:
        """Извлекает контекст вокруг имени"""
        try:
            start_pos = text.lower().find(name.lower())
            if start_pos == -1:
                return text[:min(100, len(text))]

            context_start = max(0, start_pos - context_size)
            context_end = min(len(text), start_pos + len(name) + context_size)

            context = text[context_start:context_end]

            if context_start > 0:
                context = "..." + context.lstrip()
            if context_end < len(text):
                context = context.rstrip() + "..."

            return context.strip()
        except:
            return text[:min(100, len(text))]

    def _print_collection_report(self):
        """Печатает отчет о сборе данных"""
        print(f"📊 Сбор имен завершен:")
        print(f" Обработано строк: {self.stats['lines_processed']}")
        print(f" Найдено уникальных имен: {self.stats['total_characters']}")
        print(f" Всего упоминаний: {self.stats['total_mentions']}")

        # Сортируем по уверенности и количеству упоминаний
        sorted_chars = sorted(
            self.characters.values(),
            key=lambda x: (x.mentions[0].confidence if x.mentions else 0, x.mention_count),
            reverse=True
        )

        print(f"\n🏆 Топ-15 имен персонажей:")
        for i, char in enumerate(sorted_chars[:15]):
            if not char.mentions:
                continue
            confidence = char.mentions[0].confidence
            evidence_sample = char.mentions[0].evidence[:2] if char.mentions[0].evidence else []
            print(f" {i + 1:2d}. {char.name}: {char.mention_count} упоминаний (уверенность: {confidence:.2f})")
            if evidence_sample:
                print(f"     Доказательства: {', '.join(evidence_sample)}")
            if char.mention_count > 1:
                first_line = char.mentions[0].line_idx
                last_line = char.mentions[-1].line_idx
                print(f"     Первое: строка {first_line}, последнее: строка {last_line}")

    def save_to_file(self, filename: str):
        """Сохраняет собранные данные в файл"""
        data = {
            'stats': self.stats,
            'characters': {}
        }

        for name, char_data in self.characters.items():
            data['characters'][name] = {
                'name': char_data.name,
                'mention_count': char_data.mention_count,
                'first_occurrence': char_data.first_occurrence,
                'last_occurrence': char_data.last_occurrence,
                'confidence': char_data.mentions[0].confidence if char_data.mentions else 0,
                'mentions': [
                    {
                        'line_idx': mention.line_idx,
                        'context': mention.context,
                        'line_text_preview': mention.line_text[:200],
                        'confidence': mention.confidence,
                        'evidence': mention.evidence
                    }
                    for mention in char_data.mentions
                ]
            }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"💾 Данные сохранены в: {filename}")


def run_character_collection(lines: List, save_debug: bool = False) -> Dict[str, CharacterData]:
    """
    Запускает сбор имен персонажей
    """
    collector = CharacterCollector()
    characters = collector.collect_characters(lines)

    if save_debug:
        collector.save_to_file("debug_output/character_collection.json")

    return characters
