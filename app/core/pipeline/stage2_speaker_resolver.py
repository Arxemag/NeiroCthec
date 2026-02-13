# core/pipeline/stage2_speaker_resolver.py
import re
import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from core.models import Line, UserBookFormat, Remark

# 🔥 БЕЗОПАСНЫЙ ИМПОРТ
try:
    from .stage2_0_verb_dictionary import (
        VerbDictionary,
        BookVerbAnalyzer,
        get_global_verb_dictionary,
        update_global_dictionary,
        analyze_context
    )
except ImportError:
    class VerbDictionary:
        male_verbs = set()
        female_verbs = set()
        context_indicators = {'male': set(), 'female': set()}


    class BookVerbAnalyzer:
        def analyze_book(self, lines): return VerbDictionary()


    def get_global_verb_dictionary():
        return VerbDictionary()


    def update_global_dictionary(*args):
        pass


    def analyze_context(*args):
        return "unknown", []

# 🔥 Подключение модулей Stage 2.1–2.4 (с безопасным fallback)
try:
    from .stage2_1_evidence_collectors import (
        PatternEvidenceCollector,
        PronounEvidenceCollector,
        NameEvidenceCollector,
    )
    from .stage2_2_evidence_resolver import EvidenceResolver
    from .stage2_3_context_manager import ContextManager
    from .stage2_4_fallback_strategies import ContextAwareFallback
except ImportError:
    PatternEvidenceCollector = None
    PronounEvidenceCollector = None
    NameEvidenceCollector = None
    EvidenceResolver = None
    ContextManager = None
    ContextAwareFallback = None


@dataclass
class SpeakerResolverConfig:
    # 🔥 УБРАЛ high_confidence_threshold - оставил только основные параметры
    confidence_threshold: float = 0.3
    use_narrator_fallback: bool = False
    debug_detailed: bool = True
    analyze_verbs: bool = True

    # 🔥 РАСШИРЕННЫЕ СЛОВАРИ
    female_verbs: set = field(default_factory=lambda: {
        "сказала", "доложила", "сообщила", "спросила", "ответила", "закивала",
        "улыбнулась", "кивнула", "прочистив", "начала", "ответила"
    })
    male_verbs: set = field(default_factory=lambda: {
        "сказал", "доложил", "сообщил", "спросил", "ответил", "проговорил",
        "принял", "догадался", "согласился", "решил", "послышался"
    })

    female_names: set = field(default_factory=lambda: {"лора", "анна", "мария", "девушка"})
    male_names: set = field(default_factory=lambda: {"иван", "пётр", "сергей"})


class SpeakerResolver:
    # 🔥 СБАЛАНСИРОВАННЫЕ ВЕСА
    WEIGHTS = {
        'explicit_pronoun_verb': 3.0,  # "сказал я" - самый сильный
        'verb_endings': 2.5,  # окончания глаголов
        'static_verbs': 2.0,  # глаголы из конфига
        'context_name_indicators': 1.8,  # "девушка сказала"
        'dynamic_verbs': 1.5,  # глаголы из словаря
        'pronoun_ratio': 1.2,  # местоимения
        'names': 1.0,  # имена
        'dialogue_context': 0.8,  # контекст диалога
        'context_indicators': 0.6,  # общие контекстные слова
        'book_statistics': 0.3,  # статистика книги
    }

    def __init__(self, config: Optional[SpeakerResolverConfig] = None):
        self.config = config or SpeakerResolverConfig()
        self.verb_analyzer = BookVerbAnalyzer()
        self.verb_dictionary = get_global_verb_dictionary()
        self.last_speaker = None
        self.segment_speakers = {}
        self.stats = defaultdict(int)
        self.logger = logging.getLogger(__name__)
        self.book_gender_stats = {'male': 0, 'female': 0, 'total': 0}

        # Stage 2.1–2.4 оркестрация (если модули доступны)
        self.context_manager = ContextManager() if ContextManager else None
        self.evidence_resolver = EvidenceResolver(
            confidence_threshold=self.config.confidence_threshold,
            high_confidence_threshold=max(self.config.confidence_threshold + 0.2, 0.6),
        ) if EvidenceResolver else None
        self.fallback_strategy = ContextAwareFallback(
            use_narrator_fallback=self.config.use_narrator_fallback
        ) if ContextAwareFallback else None
        self.evidence_collectors = []
        if PatternEvidenceCollector:
            pattern_map = {
                r"\b(сказал|ответил|спросил|произнёс|произнес)\b": ("male", 1.0),
                r"\b(сказала|ответила|спросила|произнесла)\b": ("female", 1.0),
                r"\b(мужчина|парень|юноша)\b": ("male", 0.8),
                r"\b(женщина|девушка)\b": ("female", 0.8),
            }
            self.evidence_collectors.append(PatternEvidenceCollector(pattern_map))
        if PronounEvidenceCollector:
            self.evidence_collectors.append(PronounEvidenceCollector(self.WEIGHTS))
        if NameEvidenceCollector:
            self.evidence_collectors.append(
                NameEvidenceCollector(self.config.female_names, self.config.male_names, self.WEIGHTS['names'])
            )

        # 🔥 ИНИЦИАЛИЗАЦИЯ ПО УМОЛЧАНИЮ
        if not hasattr(self.verb_dictionary, 'male_verbs'):
            self.verb_dictionary.male_verbs = set()
        if not hasattr(self.verb_dictionary, 'female_verbs'):
            self.verb_dictionary.female_verbs = set()
        if not hasattr(self.verb_dictionary, 'context_indicators'):
            self.verb_dictionary.context_indicators = {'male': set(), 'female': set()}

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        """ОСНОВНОЙ МЕТОД"""
        try:
            print(f"\n🎭 Stage 2 — Speaker Resolution")

            # 🔥 Анализ глаголов книги
            if self.config.analyze_verbs:
                print("🔍 Анализ глаголов и контекста книги...")
                try:
                    book_dictionary = self.verb_analyzer.analyze_book(ubf.lines)
                    update_global_dictionary(book_dictionary)
                    self.verb_dictionary = get_global_verb_dictionary()
                except Exception as e:
                    print(f"⚠️ Ошибка анализа глаголов: {e}")

            # Рассчитываем статистику книги
            self._calculate_book_gender_stats(ubf)

            # 🔥 ОБРАБОТКА С ДЕБАГ-ВЫВОДОМ
            for i, line in enumerate(sorted(ubf.lines, key=lambda l: l.idx if l.idx is not None else l.id)):
                if self.config.debug_detailed and line.type == "dialogue":
                    print(f"\n--- Line {i:04d} ---")
                    print(f"Text: {line.original[:100]}...")

                self._process_line(line, i)

            self._log_statistics(ubf)
            return ubf

        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            return ubf

    def _calculate_book_gender_stats(self, ubf: UserBookFormat):
        """Рассчитывает статистику полов по книге"""
        try:
            male_count = 0
            female_count = 0

            for line in ubf.lines:
                if line.type == "dialogue" and line.speaker:
                    if line.speaker == "male":
                        male_count += 1
                    elif line.speaker == "female":
                        female_count += 1

            self.book_gender_stats = {
                'male': male_count,
                'female': female_count,
                'total': male_count + female_count
            }
        except Exception as e:
            self.book_gender_stats = {'male': 0, 'female': 0, 'total': 0}

    def _process_line(self, line: Line, line_index: int):
        """ОБРАБОТКА СТРОКИ"""
        try:
            if line.type != "dialogue":
                line.speaker = "narrator"
                self.stats['narrator_lines'] += 1
                return

            self.stats['dialogue_lines'] += 1

            # 🔥 Сначала проверяем контекст сегмента (2.3) и локальный кэш
            if self.context_manager:
                context_speaker = self.context_manager.get_segment_speaker(line)
                if context_speaker:
                    line.speaker = context_speaker
                    self.stats['from_context'] += 1
                    self.last_speaker = line.speaker
                    return

            if line.is_segment and line.base_line_id is not None and line.base_line_id in self.segment_speakers:
                line.speaker = self.segment_speakers[line.base_line_id]
                self.stats['from_context'] += 1
                self.last_speaker = line.speaker
                return

            # 🔥 ОСНОВНОЙ АНАЛИЗ
            speaker, confidence, reasoning = self._analyze_text_with_reasoning(line)

            # 🔥 УПРОЩЕННАЯ ЛОГИКА ПРИНЯТИЯ РЕШЕНИЯ
            if speaker != "unknown" and confidence >= self.config.confidence_threshold:
                line.speaker = speaker
                self.stats['resolved'] += 1
                self.last_speaker = speaker

                if self.config.debug_detailed:
                    print(f"✅ {speaker.upper()} (conf: {confidence:.2f})")
                    for reason in reasoning[:3]:
                        print(f"   {reason}")
            else:
                # 🔥 УМНЫЙ ФОЛБЭК
                fallback_speaker, fallback_reason = self._smart_fallback(line, reasoning)
                line.speaker = fallback_speaker
                self.stats['fallback'] += 1
                self.last_speaker = fallback_speaker

                if self.config.debug_detailed:
                    print(f"🔄 {fallback_speaker.upper()} (fallback: {fallback_reason})")

            # Сохраняем для сегментов и контекста 2.3
            if line.is_segment and line.base_line_id is not None:
                self.segment_speakers[line.base_line_id] = line.speaker

            if self.context_manager:
                self.context_manager.set_segment_speaker(line, line.speaker)
                self.context_manager.update_dialogue_sequence(line.speaker)

        except Exception as e:
            print(f"⚠️ Ошибка строки {line_index}: {e}")
            line.speaker = "unknown"

    def _analyze_text_with_reasoning(self, line: Line) -> Tuple[str, float, List[str]]:
        """УПРОЩЕННЫЙ АНАЛИЗ"""
        try:
            reasoning = []
            scores = {'male': 0.0, 'female': 0.0}
            text = line.original.lower()

            # 🔥 1. САМЫЙ ВАЖНЫЙ: ЯВНЫЕ УКАЗАТЕЛИ "я" + глагол
            explicit_score = self._score_explicit_pronoun_verb(text)
            scores['male'] += explicit_score['male'] * self.WEIGHTS['explicit_pronoun_verb']
            scores['female'] += explicit_score['female'] * self.WEIGHTS['explicit_pronoun_verb']
            reasoning.extend(explicit_score['reasons'])

            # Если есть явная самореференция "глагол + я" только одного рода,
            # считаем это приоритетным сигналом спикера.
            if explicit_score['male'] > 0 and explicit_score['female'] == 0:
                reasoning.append('Приоритет: явное "глагол+я" -> male')
                return 'male', 0.95, reasoning
            if explicit_score['female'] > 0 and explicit_score['male'] == 0:
                reasoning.append('Приоритет: явное "глагол+я" -> female')
                return 'female', 0.95, reasoning

            # 🔥 2. ОКОНЧАНИЯ ГЛАГОЛОВ
            endings_score = self._score_verb_endings(text)
            scores['male'] += endings_score['male'] * self.WEIGHTS['verb_endings']
            scores['female'] += endings_score['female'] * self.WEIGHTS['verb_endings']
            reasoning.extend(endings_score['reasons'])

            # 🔥 3. СТАТИЧЕСКИЕ ГЛАГОЛЫ
            static_verbs_score = self._score_static_verbs(text)
            scores['male'] += static_verbs_score['male'] * self.WEIGHTS['static_verbs']
            scores['female'] += static_verbs_score['female'] * self.WEIGHTS['static_verbs']
            reasoning.extend(static_verbs_score['reasons'])

            # 🔥 4. КОНТЕКСТНЫЕ УКАЗАТЕЛИ С ИМЕНАМИ
            context_name_score = self._score_context_name_indicators(text)
            scores['male'] += context_name_score['male'] * self.WEIGHTS['context_name_indicators']
            scores['female'] += context_name_score['female'] * self.WEIGHTS['context_name_indicators']
            reasoning.extend(context_name_score['reasons'])

            # 🔥 5. ДИНАМИЧЕСКИЕ ГЛАГОЛЫ
            dynamic_verbs_score = self._score_dynamic_verbs(text)
            scores['male'] += dynamic_verbs_score['male'] * self.WEIGHTS['dynamic_verbs']
            scores['female'] += dynamic_verbs_score['female'] * self.WEIGHTS['dynamic_verbs']
            reasoning.extend(dynamic_verbs_score['reasons'])

            # 🔥 6. МЕСТОИМЕНИЯ
            pronouns_score = self._score_pronouns(text)
            scores['male'] += pronouns_score['male'] * self.WEIGHTS['pronoun_ratio']
            scores['female'] += pronouns_score['female'] * self.WEIGHTS['pronoun_ratio']
            reasoning.extend(pronouns_score['reasons'])

            # 🔥 7. КОНТЕКСТ ДИАЛОГА
            dialogue_score = self._score_dialogue_context()
            scores['male'] += dialogue_score['male'] * self.WEIGHTS['dialogue_context']
            scores['female'] += dialogue_score['female'] * self.WEIGHTS['dialogue_context']
            reasoning.extend(dialogue_score['reasons'])

            # 🔥 8. Stage 2.1->2.2: collect/resolve evidences
            ext_speaker, ext_conf, ext_reasons = self._resolve_with_external_modules(line)
            if ext_speaker != "unknown":
                if ext_speaker == 'male':
                    scores['male'] += max(ext_conf, 0.1)
                elif ext_speaker == 'female':
                    scores['female'] += max(ext_conf, 0.1)
                reasoning.extend(ext_reasons)

            # 🔥 ОПРЕДЕЛЯЕМ ПОБЕДИТЕЛЯ
            return self._determine_winner_simple(scores, reasoning)

        except Exception as e:
            return "unknown", 0.0, [f"Ошибка: {e}"]

    def _score_explicit_pronoun_verb(self, text: str) -> Dict:
        """Поиск конструкций 'глагол + я'"""
        score = {'male': 0, 'female': 0, 'reasons': []}

        try:
            if " я" not in text and "я " not in text:
                return score

            patterns = [
                (r'(\S+л)[,–—-]*\s+я\b', 'male'),  # "сказал я" (+ пунктуация)
                (r'(\S+ла)[,–—-]*\s+я\b', 'female'),  # "сказала я" (+ пунктуация)
                (r'\bя\s+(\S+л)\b', 'male'),  # "я сказал"
                (r'\bя\s+(\S+ла)\b', 'female'),  # "я сказала"
                (r'\bя\s+(\S+лся)\b', 'male'),  # "я оказался"
                (r'\bя\s+(\S+лась)\b', 'female')  # "я оказалась"
            ]

            for pattern, gender in patterns:
                matches = re.findall(pattern, text)
                for verb in matches:
                    if gender == 'male':
                        score['male'] += 1
                        score['reasons'].append(f"Явный: '{verb} я'")
                    else:
                        score['female'] += 1
                        score['reasons'].append(f"Явный: '{verb} я'")

        except re.error:
            pass

        return score

    def _score_verb_endings(self, text: str) -> Dict:
        """Анализ окончаний"""
        score = {'male': 0, 'female': 0, 'reasons': []}

        try:
            male_patterns = [r'\b\S+л\b', r'\b\S+лся\b']
            female_patterns = [r'\b\S+ла\b', r'\b\S+лась\b']

            male_count = sum(len(re.findall(pattern, text)) for pattern in male_patterns)
            female_count = sum(len(re.findall(pattern, text)) for pattern in female_patterns)

            score['male'] = male_count
            score['female'] = female_count

            if male_count > 0:
                score['reasons'].append(f"Глаголы м.р.: {male_count}")
            if female_count > 0:
                score['reasons'].append(f"Глаголы ж.р.: {female_count}")

        except Exception:
            pass

        return score

    def _score_static_verbs(self, text: str) -> Dict:
        """Глаголы из конфига"""
        score = {'male': 0, 'female': 0, 'reasons': []}

        try:
            for verb in self.config.male_verbs:
                if re.search(rf'\b{re.escape(verb)}\b', text):
                    score['male'] += 1
                    score['reasons'].append(f"Глагол м.р.: '{verb}'")

            for verb in self.config.female_verbs:
                if re.search(rf'\b{re.escape(verb)}\b', text):
                    score['female'] += 1
                    score['reasons'].append(f"Глагол ж.р.: '{verb}'")

        except Exception:
            pass

        return score

    def _score_context_name_indicators(self, text: str) -> Dict:
        """Контекстные указатели"""
        score = {'male': 0, 'female': 0, 'reasons': []}

        try:
            if re.search(r'\bдевушка\b', text):
                score['female'] += 1
                score['reasons'].append("Контекст: 'девушка'")

            if re.search(r'\bженский\b', text):
                score['female'] += 1
                score['reasons'].append("Контекст: 'женский'")

            if re.search(r'\bмужчин', text):
                score['male'] += 1
                score['reasons'].append("Контекст: 'мужчин'")

        except Exception:
            pass

        return score

    def _score_dynamic_verbs(self, text: str) -> Dict:
        """Глаголы из словаря"""
        score = {'male': 0, 'female': 0, 'reasons': []}

        try:
            for verb in getattr(self.verb_dictionary, 'male_verbs', set()):
                safe_verb = re.escape(verb)
                if re.search(rf'\b{safe_verb}\b', text):
                    score['male'] += 1
                    score['reasons'].append(f"Словарь м.р.: '{verb}'")

            for verb in getattr(self.verb_dictionary, 'female_verbs', set()):
                safe_verb = re.escape(verb)
                if re.search(rf'\b{safe_verb}\b', text):
                    score['female'] += 1
                    score['reasons'].append(f"Словарь ж.р.: '{verb}'")

        except Exception:
            pass

        return score

    def _score_pronouns(self, text: str) -> Dict:
        """Местоимения"""
        score = {'male': 0, 'female': 0, 'reasons': []}

        try:
            male_count = len(re.findall(r'\bон\b', text))
            female_count = len(re.findall(r'\bона\b', text))

            score['male'] = male_count
            score['female'] = female_count

            if male_count > 0 or female_count > 0:
                score['reasons'].append(f"Местоимения: м={male_count}, ж={female_count}")

        except Exception:
            pass

        return score

    def _score_dialogue_context(self) -> Dict:
        """Контекст диалога"""
        score = {'male': 0, 'female': 0, 'reasons': []}

        if self.last_speaker and self.last_speaker != "narrator":
            if self.last_speaker == "male":
                score['female'] += 1
                score['reasons'].append("Контекст: предыдущий male")
            else:
                score['male'] += 1
                score['reasons'].append("Контекст: предыдущий female")

        return score

    def _determine_winner_simple(self, scores: Dict, reasoning: List[str]) -> Tuple[str, float, List[str]]:
        """ПРОСТОЕ ОПРЕДЕЛЕНИЕ ПОБЕДИТЕЛЯ"""
        try:
            total_male = scores['male']
            total_female = scores['female']

            if total_male == 0 and total_female == 0:
                return "unknown", 0.0, reasoning + ["Нет доказательств"]

            if total_male > total_female:
                confidence = (total_male - total_female) / max(total_male + total_female, 1)
                reasoning.append(f"РЕШЕНИЕ: male ({total_male} > {total_female})")
                return "male", confidence, reasoning
            elif total_female > total_male:
                confidence = (total_female - total_male) / max(total_male + total_female, 1)
                reasoning.append(f"РЕШЕНИЕ: female ({total_female} > {total_male})")
                return "female", confidence, reasoning
            else:
                reasoning.append(f"НИЧЬЯ: male={total_male}, female={total_female}")
                return "unknown", 0.0, reasoning

        except Exception as e:
            return "unknown", 0.0, [f"Ошибка: {e}"]

    def _smart_fallback(self, line: Line, previous_reasons: List[str]) -> Tuple[str, str]:
        """УМНЫЙ ФОЛБЭК + Stage 2.4 strategy."""
        if self.fallback_strategy and self.context_manager:
            try:
                doc_stats = {
                    'male_ratio': self.book_gender_stats['male'] / max(self.book_gender_stats['total'], 1),
                    'female_ratio': self.book_gender_stats['female'] / max(self.book_gender_stats['total'], 1),
                }
                fallback = self.fallback_strategy.get_fallback_speaker(line, self.context_manager, doc_stats)
                if fallback:
                    return fallback, "fallback_strategy(2.4)"
            except Exception:
                pass

        text_lower = line.original.lower()

        male_verbs = len(re.findall(r'\b\S+л\b', text_lower))
        female_verbs = len(re.findall(r'\b\S+ла\b', text_lower))

        if male_verbs > female_verbs:
            return "male", f"глаголы м.р. ({male_verbs} vs {female_verbs})"
        elif female_verbs > male_verbs:
            return "female", f"глаголы ж.р. ({male_verbs} vs {female_verbs})"

        if self.last_speaker and self.last_speaker != "narrator":
            return "female" if self.last_speaker == "male" else "male", "чередование"

        return "male", "умолчание"

    def _resolve_with_external_modules(self, line: Line) -> Tuple[str, float, List[str]]:
        """Stage 2.1 -> 2.2 pipeline (collect evidences + resolve)."""
        if not self.evidence_collectors or not self.evidence_resolver:
            return "unknown", 0.0, []

        all_evidences = []
        for collector in self.evidence_collectors:
            try:
                all_evidences.extend(collector.collect(line))
            except Exception:
                continue

        if not all_evidences:
            return "unknown", 0.0, []

        result = self.evidence_resolver.resolve(all_evidences)
        reasons = [
            f"2.1/2.2: {ev.source}:{ev.details} w={ev.weight:.2f}" for ev in result.used_evidences[:4]
        ]
        return result.speaker, result.confidence, reasons

    def _log_statistics(self, ubf: UserBookFormat):
        """Логирование статистики"""
        try:
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

            # Распределение спикеров
            speakers = {}
            for line in ubf.lines:
                if line.speaker:
                    speakers[line.speaker] = speakers.get(line.speaker, 0) + 1

            print("\nРаспределение спикеров:")
            for speaker, count in speakers.items():
                pct = (count / max(total_lines, 1)) * 100
                print(f"  {speaker}: {count} строк ({pct:.1f}%)")

        except Exception as e:
            print(f"⚠️ Ошибка статистики: {e}")
