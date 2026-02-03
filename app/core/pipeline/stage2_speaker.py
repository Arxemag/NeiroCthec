# core/pipeline/stage2_speaker.py
import re
import logging
from typing import Optional, List, Dict
from collections import deque, defaultdict
from dataclasses import dataclass, field

from core.models import Line, UserBookFormat, Remark


@dataclass
class SpeakerConfig:
    """Конфигурация резолвера спикеров"""
    # Основные настройки
    use_simple_rules: bool = True  # 🔥 ВКЛЮЧАЕМ простые правила
    use_natasha: bool = False  # 🔥 ОТКЛЮЧАЕМ Natasha пока что
    fallback_to_narrator: bool = False  # 🔥 НЕ фолбэкаем на narrator в диалогах

    # Правила для простого определения
    explicit_patterns: Dict[str, str] = field(default_factory=lambda: {
        r'доложил[а]?\s+он[ауе]?': 'female',
        r'сказал[а]?\s+он[ауе]?': 'male',
        r'ответил[а]?\s+он[ауе]?': 'male',
        r'произн[её]с[ла]?\s+он[ауе]?': 'male',
        r'промолвил[а]?\s+он[ауе]?': 'male',
        r'воскликнул[а]?\s+он[ауе]?': 'male',
        r'заметил[а]?\s+он[ауе]?': 'male',
        r'повторил[а]?\s+он[ауе]?': 'male',
        r'добавил[а]?\s+он[ауе]?': 'male',
        r'спросил[а]?\s+он[ауе]?': 'male',
        r'крикнул[а]?\s+он[ауе]?': 'male',
        r'прошептал[а]?\s+он[ауе]?': 'male',
        r'подумал[а]?\s+он[ауе]?': 'male',
        r'буркнул[а]?\s+он[ауе]?': 'male',
    })

    # Логирование
    log_level: int = logging.INFO

    # Словари имён
    female_names: set = field(default_factory=lambda: {
        "анна", "мария", "екатерина", "ольга", "дина", "наталья", "елена",
        "светлана", "ирина", "юлия", "татьяна", "людмила"
    })

    male_names: set = field(default_factory=lambda: {
        "иван", "пётр", "сергей", "алексей", "василий", "андрей", "дмитрий",
        "михаил", "владимир", "николай", "александр", "евгений", "павел"
    })


class SpeakerResolver:
    """
    Stage 2 — SpeakerResolver
    🔥 ИСПРАВЛЕН: Работает с обновлённой моделью, использует простые правила
    """

    def __init__(self, config: Optional[SpeakerConfig] = None):
        self.config = config or SpeakerConfig()

        # Контекст для сегментов
        self.speaker_context: Dict[int, str] = {}  # base_line_id -> speaker
        self.last_dialogue_speaker: Optional[str] = None

        # Статистика
        self.stats = defaultdict(int)

        # Логирование
        logging.basicConfig(level=self.config.log_level)
        self.logger = logging.getLogger(__name__)

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        """Обработка всех строк"""
        self.stats['total_lines'] = len(ubf.lines)

        print(f"\n🎭 Stage 2: Определение спикеров")

        for line in sorted(ubf.lines, key=lambda l: l.idx):
            self._resolve_line(line)

        self._log_statistics()
        return ubf

    def _resolve_line(self, line: Line) -> None:
        """Определение спикера для строки"""
        if line.type != "dialogue":
            line.speaker = "narrator"
            self.stats['narrator_lines'] += 1
            return

        self.stats['dialogue_lines'] += 1

        # 🔥 1. Если это сегмент, проверяем контекст
        if line.is_segment and line.base_line_id is not None:
            if line.base_line_id in self.speaker_context:
                line.speaker = self.speaker_context[line.base_line_id]
                self.stats['from_context'] += 1
                self.logger.debug(f"Line {line.idx}: speaker from context = {line.speaker}")
                return

        # 🔥 2. Простой анализ текста
        speaker = self._analyze_text_simple(line)

        if speaker != "unknown":
            line.speaker = speaker
            self.stats['resolved'] += 1

            # Сохраняем в контекст для сегментов
            if line.is_segment and line.base_line_id is not None:
                self.speaker_context[line.base_line_id] = speaker

            self.last_dialogue_speaker = speaker
            self.logger.debug(f"Line {line.idx}: resolved = {speaker}")
            return

        # 🔥 3. Фолбэк: если диалог и не определили, ставим male/female по контексту
        if self.last_dialogue_speaker and self.last_dialogue_speaker != "narrator":
            line.speaker = self.last_dialogue_speaker
            self.stats['fallback_context'] += 1
        elif not self.config.fallback_to_narrator:
            # Если диалог - пробуем male, а не narrator
            line.speaker = "male"
            self.stats['fallback_male'] += 1
        else:
            line.speaker = "narrator"
            self.stats['fallback_narrator'] += 1

        # Сохраняем в контекст
        if line.is_segment and line.base_line_id is not None:
            self.speaker_context[line.base_line_id] = line.speaker

        self.last_dialogue_speaker = line.speaker

    def _analyze_text_simple(self, line: Line) -> str:
        """
        🔥 ПРОСТОЙ И ЭФФЕКТИВНЫЙ АНАЛИЗ ТЕКСТА
        Ищет явные указания на пол в оригинальном тексте и ремарках
        """
        # Собираем весь текст для анализа
        text_to_analyze = line.original.lower()

        # Добавляем ремарки
        if line.remarks:
            for remark in line.remarks:
                text_to_analyze += " " + remark.text.lower()

        # 1. Ищем явные паттерны из конфига
        for pattern, gender in self.config.explicit_patterns.items():
            if re.search(pattern, text_to_analyze, re.IGNORECASE):
                self.logger.debug(f"Found pattern '{pattern}' -> {gender}")
                return gender

        # 2. Простые ключевые слова (более надёжные)
        simple_patterns = [
            # Женские паттерны
            (r'\bдоложила\s+(?:ей?|мне|нам|ему|ей|им|ей)\b', 'female'),
            (r'\b(?:ей?|мне|нам|ему|ей|им|ей)\s+доложила\b', 'female'),
            (r'\bсказала\s+(?:ей?|мне|нам|ему|ей|им|ей)\b', 'female'),
            (r'\b(?:ей?|мне|нам|ему|ей|им|ей)\s+сказала\b', 'female'),
            (r'\bответила\s+(?:ей?|мне|нам|ему|ей|им|ей)\b', 'female'),

            # Мужские паттерны
            (r'\bдоложил\s+(?:ей?|мне|нам|ему|ей|им|ей)\b', 'male'),
            (r'\b(?:ей?|мне|нам|ему|ей|им|ей)\s+доложил\b', 'male'),
            (r'\bсказал\s+(?:ей?|мне|нам|ему|ей|им|ей)\b', 'male'),
            (r'\b(?:ей?|мне|нам|ему|ей|им|ей)\s+сказал\b', 'male'),
            (r'\bответил\s+(?:ей?|мне|нам|ему|ей|им|ей)\b', 'male'),

            # С местоимениями
            (r'\bдоложила\s+она\b', 'female'),
            (r'\bона\s+доложила\b', 'female'),
            (r'\bсказала\s+она\b', 'female'),
            (r'\bона\s+сказала\b', 'female'),

            (r'\bдоложил\s+он\b', 'male'),
            (r'\bон\s+доложил\b', 'male'),
            (r'\bсказал\s+он\b', 'male'),
            (r'\bон\s+сказал\b', 'male'),
        ]

        for pattern, gender in simple_patterns:
            if re.search(pattern, text_to_analyze, re.IGNORECASE):
                self.logger.debug(f"Found simple pattern '{pattern}' -> {gender}")
                return gender

        # 3. Подсчёт местоимений
        male_pronouns = len(re.findall(r'\bон[ауе]?\b', text_to_analyze))
        female_pronouns = len(re.findall(r'\bона\b', text_to_analyze))

        if male_pronouns > female_pronouns * 2:
            return "male"
        elif female_pronouns > male_pronouns * 2:
            return "female"

        # 4. Имена в тексте
        if self._contains_female_name(text_to_analyze):
            return "female"
        if self._contains_male_name(text_to_analyze):
            return "male"

        return "unknown"

    def _contains_female_name(self, text: str) -> bool:
        """Проверяет наличие женских имён в тексте"""
        for name in self.config.female_names:
            if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                return True
        return False

    def _contains_male_name(self, text: str) -> bool:
        """Проверяет наличие мужских имён в тексте"""
        for name in self.config.male_names:
            if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                return True
        return False

    def _log_statistics(self):
        """Логирование статистики"""
        total = self.stats['total_lines']
        dialogue = self.stats.get('dialogue_lines', 0)

        print(f"  Всего строк: {total}")
        print(f"  Диалоговых: {dialogue}")

        if dialogue > 0:
            print(f"  Успешно определено: {self.stats.get('resolved', 0)}")
            print(f"  Из контекста: {self.stats.get('from_context', 0)}")
            print(f"  Фолбэк по контексту: {self.stats.get('fallback_context', 0)}")
            print(f"  Фолбэк male: {self.stats.get('fallback_male', 0)}")
            print(f"  Фолбэк narrator: {self.stats.get('fallback_narrator', 0)}")

        # Распределение спикеров
        speakers = {}
        for line in [l for l in self._last_ubf.lines if l.speaker]:
            speakers[line.speaker] = speakers.get(line.speaker, 0) + 1

        if speakers:
            print(f"  Распределение спикеров: {speakers}")

    # Для статистики
    _last_ubf = None

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        self._last_ubf = ubf
        return super().process(ubf)