# core/pipeline/stage2_speaker_resolver.py
import re
import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from core.models import Line, UserBookFormat, Remark


@dataclass
class SpeakerResolverConfig:
    """ИСПРАВЛЕННАЯ конфигурация"""
    confidence_threshold: float = 1.5
    high_confidence_threshold: float = 2.0
    use_narrator_fallback: bool = False
    debug_detailed: bool = True

    # 🔥🔥🔥 ПЕРЕПИСЫВАЕМ ПАТТЕРНЫ ПРАВИЛЬНО!
    patterns: Dict[str, Tuple[str, float]] = field(default_factory=lambda: {
        # 🔥 ОБЩИЕ ПАТТЕРНЫ С АВТООПРЕДЕЛЕНИЕМ ПО ГЛАГОЛУ
        r'([а-я]+л[а])\s+он[а]?': ('verb_gender', 3.0),  # Сначала определяем род глагола!
    })

    # 🔥 ОТДЕЛЬНЫЕ СЛОВАРЯ ГЛАГОЛОВ
    female_verbs: set = field(default_factory=lambda: {
        "сказала", "доложила", "сообщила", "спросила", "ответила", "прошептала",
        "произнесла", "промолвила", "воскликнула", "заметила", "добавила"
    })
    male_verbs: set = field(default_factory=lambda: {
        "сказал", "доложил", "сообщил", "спросил", "ответил", "прошептал",
        "произнес", "промолвил", "воскликнул", "заметил", "добавил", "скомандовал", "выдохнул"
    })

    female_names: set = field(default_factory=lambda: {"лора", "анна", "мария", "екатерина", "ольга"})
    male_names: set = field(default_factory=lambda: {"иван", "пётр", "сергей", "алексей"})


class SpeakerResolver:
    """ИСПРАВЛЕННАЯ версия резолвера"""

    def __init__(self, config: Optional[SpeakerResolverConfig] = None):
        self.config = config or SpeakerResolverConfig()
        self.last_speaker = None
        self.segment_speakers = {}
        self.stats = defaultdict(int)
        self.logger = logging.getLogger(__name__)

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        print(f"\n🎭 Stage 2 — Speaker Resolution")
        print("🔥 ИСПРАВЛЕННЫЙ АЛГОРИТМ")

        for i, line in enumerate(sorted(ubf.lines, key=lambda l: l.idx)):
            self._process_line(line, i)

        self._log_statistics(ubf)
        return ubf

    def _process_line(self, line: Line, line_index: int):
        if line.type != "dialogue":
            line.speaker = "narrator"
            self.stats['narrator_lines'] += 1
            return

        self.stats['dialogue_lines'] += 1

        # Проверка контекста сегментов
        if line.is_segment and line.base_line_id is not None and line.base_line_id in self.segment_speakers:
            line.speaker = self.segment_speakers[line.base_line_id]
            self.stats['from_context'] += 1
            self.last_speaker = line.speaker
            return

        # 🔥🔥🔥 ИСПРАВЛЕННЫЙ АНАЛИЗ С ПРАВИЛЬНЫМИ ПРИОРИТЕТАМИ
        speaker, confidence, reasoning = self._analyze_text_with_reasoning(line)

        if speaker != "unknown":
            line.speaker = speaker
            self.stats['resolved'] += 1

            if self.config.debug_detailed:
                print(f"✅ Line {line_index}: {speaker} (confidence: {confidence:.2f})")
                for reason in reasoning:
                    print(f"   {reason}")
        else:
            # 🔥 ИСПРАВЛЕННЫЙ ФОЛБЭК
            if self.last_speaker and self.last_speaker != "narrator":
                # Чередуем male/female чтобы избежать цепной реакции
                if self.last_speaker == "male":
                    line.speaker = "female"
                    fallback_reason = "alternating (male→female)"
                else:
                    line.speaker = "male"
                    fallback_reason = "alternating (female→male)"
            else:
                line.speaker = "male"
                fallback_reason = "default"
            self.stats['fallback'] += 1

            if self.config.debug_detailed:
                print(f"🔄 Line {line_index}: {line.speaker} (fallback: {fallback_reason})")

        # Сохраняем контекст
        if line.is_segment and line.base_line_id is not None:
            self.segment_speakers[line.base_line_id] = line.speaker

        self.last_speaker = line.speaker

    def _analyze_text_with_reasoning(self, line: Line) -> Tuple[str, float, List[str]]:
        """Анализ с возвратом причин"""
        reasoning = []
        text = line.original.lower()
        remarks_text = ""

        if line.remarks:
            for remark in line.remarks:
                remarks_text += " " + remark.text.lower()

        full_text = text + remarks_text

        # 🔥 1. АНАЛИЗ ГЛАГОЛОВ (САМЫЙ ВАЖНЫЙ!)
        verb_gender, verb_reason = self._analyze_verbs_detailed(full_text)
        if verb_gender != "unknown":
            reasoning.extend(verb_reason)
            return verb_gender, 3.0, reasoning

        # 🔥 2. ПАТТЕРНЫ С АВТООПРЕДЕЛЕНИЕМ ПО ГЛАГОЛУ
        for pattern, (gender_type, weight) in self.config.patterns.items():
            match = re.search(pattern, full_text)
            if match:
                if gender_type == "verb_gender":
                    verb = match.group(1) if match.groups() else ""
                    detected_gender = self._detect_gender_by_verb(verb)
                    if detected_gender != "unknown":
                        reasoning.append(f"Паттерн глагола: '{verb}' → {detected_gender}")
                        return detected_gender, weight, reasoning

        # 🔥 3. МЕСТОИМЕНИЯ (менее надежно)
        male_pronouns = len(re.findall(r'\bон[ауе]?\b', full_text))
        female_pronouns = len(re.findall(r'\bона\b', full_text))

        if male_pronouns > 0 or female_pronouns > 0:
            reasoning.append(f"Местоимения: 👨={male_pronouns}, 👩={female_pronouns}")

            if male_pronouns > female_pronouns * 2:
                reasoning.append("Преобладают мужские местоимения → male")
                return "male", 1.5, reasoning
            elif female_pronouns > male_pronouns * 2:
                reasoning.append("Преобладают женские местоимения → female")
                return "female", 1.5, reasoning

        # 🔥 4. ИМЕНА (самый ненадежный - используем только как доп. признак)
        name_gender, name_reason = self._analyze_names_detailed(full_text)
        if name_gender != "unknown":
            reasoning.extend(name_reason)
            return name_gender, 1.2, reasoning

        reasoning.append("Не удалось определить")
        return "unknown", 0.0, reasoning

    def _analyze_verbs_detailed(self, text: str) -> Tuple[str, List[str]]:
        """Детальный анализ глаголов"""
        reasoning = []

        # Ищем конкретные глаголы
        found_verbs = []
        for verb in self.config.female_verbs:
            if re.search(rf'\b{verb}\b', text):
                found_verbs.append((verb, "female"))

        for verb in self.config.male_verbs:
            if re.search(rf'\b{verb}\b', text):
                found_verbs.append((verb, "male"))

        if found_verbs:
            # Берем первый найденный глагол (самый надежный)
            verb, gender = found_verbs[0]
            reasoning.append(f"Найден глагол: '{verb}' → {gender}")
            return gender, reasoning

        reasoning.append("Глаголы не найдены")
        return "unknown", reasoning

    def _analyze_names_detailed(self, text: str) -> Tuple[str, List[str]]:
        """Детальный анализ имен"""
        reasoning = []
        found_names = []

        for name in self.config.female_names:
            if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                found_names.append((name, "female"))

        for name in self.config.male_names:
            if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                found_names.append((name, "male"))

        if found_names:
            name, gender = found_names[0]
            reasoning.append(f"Найдено имя: '{name}' → {gender}")
            return gender, reasoning

        reasoning.append("Имена не найдены")
        return "unknown", reasoning

    def _detect_gender_by_verb(self, verb: str) -> str:
        """Определяет пол по окончанию глагола"""
        if verb.endswith('ла'):  # сказала, доложила, сообщила
            return "female"
        elif verb.endswith('л'):  # сказал, доложил, сообщил
            return "male"
        return "unknown"

    def _log_statistics(self, ubf: UserBookFormat):
        print("\n📊 Статистика SpeakerResolver:")
        print("=" * 40)

        total_lines = len(ubf.lines)
        dialogue_lines = self.stats.get('dialogue_lines', 0)

        print(f"Всего строк: {total_lines}")
        print(f"Диалоговых: {dialogue_lines}")

        if dialogue_lines > 0:
            print(f"Определено аналитикой: {self.stats.get('resolved', 0)}")
            print(f"Из контекста: {self.stats.get('from_context', 0)}")
            print(f"Фолбэк: {self.stats.get('fallback', 0)}")

        # Анализ качества
        print("\n🔍 АНАЛИЗ КАЧЕСТВА:")
        dialogue_lines_list = [l for l in ubf.lines if l.type == "dialogue"]

        correct = 0
        incorrect = 0

        for line in dialogue_lines_list:
            text_lower = line.original.lower()
            expected = None

            # Определяем ожидаемый пол по глаголам
            if any(verb in text_lower for verb in self.config.male_verbs):
                expected = "male"
            elif any(verb in text_lower for verb in self.config.female_verbs):
                expected = "female"

            if expected:
                if line.speaker == expected:
                    correct += 1
                else:
                    incorrect += 1
                    print(f"❌ Line: {text_lower[:60]}...")
                    print(f"   Ожидалось: {expected}, Получено: {line.speaker}")

        if correct + incorrect > 0:
            accuracy = (correct / (correct + incorrect)) * 100
            print(f"Точность: {correct}/{correct + incorrect} ({accuracy:.1f}%)")

        # Распределение спикеров
        speakers = {}
        for line in ubf.lines:
            if line.speaker:
                speakers[line.speaker] = speakers.get(line.speaker, 0) + 1

        print("\nРаспределение спикеров:")
        for speaker, count in speakers.items():
            pct = (count / total_lines) * 100
            print(f"  {speaker}: {count} строк ({pct:.1f}%)")
