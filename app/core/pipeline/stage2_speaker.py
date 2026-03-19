# core/pipeline/stage2_speaker.py
"""
Stage 2 — SpeakerResolver с модульной архитектурой.
Интегрирует stage2_0 - stage2_4 для точного определения пола спикера.
"""
import re
import logging
import builtins
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

from core.models import Line, UserBookFormat, Remark

# Безопасный импорт модулей Stage 2.x
try:
    from .stage2_0_verb_dictionary import (
        VerbDictionary,
        BookVerbAnalyzer,
        get_global_verb_dictionary,
        update_global_dictionary,
        analyze_context
    )
except ImportError:
    VerbDictionary = None
    BookVerbAnalyzer = None
    get_global_verb_dictionary = lambda: None
    update_global_dictionary = lambda x: None
    analyze_context = lambda t, d: ("unknown", [])

try:
    from .stage2_1_evidence_collectors import (
        PatternEvidenceCollector,
        PronounEvidenceCollector,
        NameEvidenceCollector,
        VerbEndingEvidenceCollector,
        ExplicitPronounVerbCollector,
        Evidence,
    )
except ImportError:
    PatternEvidenceCollector = None
    PronounEvidenceCollector = None
    NameEvidenceCollector = None
    VerbEndingEvidenceCollector = None
    ExplicitPronounVerbCollector = None
    Evidence = None

try:
    from .stage2_2_evidence_resolver import EvidenceResolver
except ImportError:
    EvidenceResolver = None

try:
    from .stage2_3_context_manager import ContextManager
except ImportError:
    ContextManager = None

try:
    from .stage2_4_fallback_strategies import ContextAwareFallback, StatisticalFallback
except ImportError:
    ContextAwareFallback = None
    StatisticalFallback = None


def _safe_print(*args, **kwargs):
    """Print wrapper that ignores ValueError: I/O operation on closed file."""
    try:
        builtins.print(*args, **kwargs)
    except ValueError:
        pass


@dataclass
class SpeakerConfig:
    """Конфигурация резолвера спикеров"""
    confidence_threshold: float = 0.3
    use_narrator_fallback: bool = False
    debug_detailed: bool = False
    analyze_verbs: bool = True
    log_level: int = logging.INFO

    female_verbs: set = field(default_factory=lambda: {
        "сказала", "доложила", "сообщила", "спросила", "ответила", "закивала",
        "улыбнулась", "кивнула", "прочистив", "начала", "ответила"
    })
    male_verbs: set = field(default_factory=lambda: {
        "сказал", "доложил", "сообщил", "спросил", "ответил", "проговорил",
        "принял", "догадался", "согласился", "решил", "послышался"
    })

    female_names: set = field(default_factory=lambda: {
        "анна", "мария", "екатерина", "ольга", "дина", "наталья", "елена",
        "светлана", "ирина", "юлия", "татьяна", "людмила", "лора", "девушка",
        "александра", "виктория", "дарья", "ксения", "анастасия", "полина"
    })

    male_names: set = field(default_factory=lambda: {
        "иван", "пётр", "сергей", "алексей", "василий", "андрей", "дмитрий",
        "михаил", "владимир", "николай", "александр", "евгений", "павел"
    })


# Веса для разных типов доказательств
WEIGHTS = {
    'explicit_pronoun_verb': 3.0,
    'verb_endings': 2.5,
    'static_verbs': 2.0,
    'context_name_indicators': 1.8,
    'dynamic_verbs': 1.5,
    'pronoun_ratio': 1.2,
    'names': 1.0,
    'dialogue_context': 0.8,
    'context_indicators': 0.6,
    'book_statistics': 0.3,
}


class SpeakerResolver:
    """
    Stage 2 — SpeakerResolver с модульной архитектурой.
    Использует систему весов и модули 2.0-2.4 для точного определения.
    """

    def __init__(self, config: Optional[SpeakerConfig] = None):
        self.config = config or SpeakerConfig()
        self.logger = logging.getLogger(__name__)

        # Модули Stage 2.x
        self.verb_analyzer = BookVerbAnalyzer() if BookVerbAnalyzer else None
        self.verb_dictionary = get_global_verb_dictionary() if get_global_verb_dictionary else None
        self.context_manager = ContextManager() if ContextManager else None
        self.evidence_resolver = EvidenceResolver(
            confidence_threshold=self.config.confidence_threshold
        ) if EvidenceResolver else None
        self.fallback_strategy = ContextAwareFallback(
            use_narrator_fallback=self.config.use_narrator_fallback
        ) if ContextAwareFallback else None
        self.stats_fallback = StatisticalFallback() if StatisticalFallback else None

        # Коллекторы доказательств
        self.evidence_collectors = []
        if ExplicitPronounVerbCollector:
            self.evidence_collectors.append(ExplicitPronounVerbCollector(WEIGHTS['explicit_pronoun_verb']))
        if VerbEndingEvidenceCollector:
            self.evidence_collectors.append(VerbEndingEvidenceCollector(WEIGHTS['verb_endings']))
        if PatternEvidenceCollector:
            self.evidence_collectors.append(PatternEvidenceCollector())
        if PronounEvidenceCollector:
            self.evidence_collectors.append(PronounEvidenceCollector(WEIGHTS))
        if NameEvidenceCollector:
            self.evidence_collectors.append(NameEvidenceCollector(
                self.config.female_names, self.config.male_names, WEIGHTS['names']
            ))

        # Локальный кэш и статистика
        self.segment_speakers: Dict[int, str] = {}
        self.last_speaker: Optional[str] = None
        self.stats = defaultdict(int)
        self.book_gender_stats = {'male': 0, 'female': 0, 'total': 0}
        self._last_ubf = None

    def process(self, ubf: UserBookFormat) -> UserBookFormat:
        """Основной метод обработки"""
        self._last_ubf = ubf
        self.stats['total_lines'] = len(ubf.lines)

        _safe_print(f"\nStage 2: Определение спикеров (модульная версия)")

        # Анализ глаголов книги
        if self.config.analyze_verbs and self.verb_analyzer:
            try:
                book_dictionary = self.verb_analyzer.analyze_book(ubf.lines)
                if update_global_dictionary:
                    update_global_dictionary(book_dictionary)
                self.verb_dictionary = get_global_verb_dictionary()
            except Exception as e:
                _safe_print(f"  Предупреждение: ошибка анализа глаголов: {e}")

        # Обработка строк
        for line in sorted(ubf.lines, key=lambda l: l.idx):
            self._process_line(line)

        self._log_statistics()
        return ubf

    def _process_line(self, line: Line):
        """Обработка одной строки"""
        if line.type != "dialogue":
            line.speaker = "narrator"
            self.stats['narrator_lines'] += 1
            return

        self.stats['dialogue_lines'] += 1

        # 1. Проверяем кэш контекста (для сегментов)
        if self.context_manager:
            context_speaker = self.context_manager.get_segment_speaker(line)
            if context_speaker:
                line.speaker = context_speaker
                self.stats['from_context'] += 1
                self.last_speaker = context_speaker
                return

        if line.is_segment and line.base_line_id is not None:
            if line.base_line_id in self.segment_speakers:
                line.speaker = self.segment_speakers[line.base_line_id]
                self.stats['from_context'] += 1
                self.last_speaker = line.speaker
                return

        # 2. Сбор и анализ доказательств
        speaker, confidence, reasoning = self._analyze_with_evidences(line)

        if speaker != "unknown" and confidence >= self.config.confidence_threshold:
            line.speaker = speaker
            self.stats['resolved'] += 1
            self.last_speaker = speaker

            if self.config.debug_detailed:
                _safe_print(f"  Line {line.idx}: {speaker} (conf={confidence:.2f})")
        else:
            # 3. Фолбэк
            fallback_speaker, fallback_reason = self._smart_fallback(line)
            line.speaker = fallback_speaker
            self.stats['fallback'] += 1
            self.last_speaker = fallback_speaker

            if self.config.debug_detailed:
                _safe_print(f"  Line {line.idx}: {fallback_speaker} (fallback: {fallback_reason})")

        # Сохраняем в кэш
        if line.is_segment and line.base_line_id is not None:
            self.segment_speakers[line.base_line_id] = line.speaker

        if self.context_manager:
            self.context_manager.set_segment_speaker(line, line.speaker)
            self.context_manager.update_dialogue_sequence(line.speaker)

        if self.stats_fallback and line.speaker in ('male', 'female'):
            self.stats_fallback.update_stats(line.speaker)

    def _analyze_with_evidences(self, line: Line) -> Tuple[str, float, List[str]]:
        """Анализ с использованием коллекторов доказательств"""
        all_evidences = []
        reasoning = []

        # Собираем доказательства от всех коллекторов
        for collector in self.evidence_collectors:
            try:
                evidences = collector.collect(line)
                all_evidences.extend(evidences)
            except Exception:
                continue

        # Добавляем доказательства из динамического словаря
        if self.verb_dictionary:
            text = line.original.lower()
            for verb in getattr(self.verb_dictionary, 'male_verbs', set()):
                if re.search(rf'\b{re.escape(verb)}\b', text):
                    if Evidence:
                        all_evidences.append(Evidence(
                            gender='male',
                            weight=WEIGHTS['dynamic_verbs'],
                            source='dynamic_verb',
                            details=f"Словарь: '{verb}'"
                        ))

            for verb in getattr(self.verb_dictionary, 'female_verbs', set()):
                if re.search(rf'\b{re.escape(verb)}\b', text):
                    if Evidence:
                        all_evidences.append(Evidence(
                            gender='female',
                            weight=WEIGHTS['dynamic_verbs'],
                            source='dynamic_verb',
                            details=f"Словарь: '{verb}'"
                        ))

        # Добавляем контекст чередования
        if self.context_manager and self.last_speaker:
            expected = self.context_manager.get_expected_speaker_by_alternation()
            if expected and Evidence:
                all_evidences.append(Evidence(
                    gender=expected,
                    weight=WEIGHTS['dialogue_context'],
                    source='alternation',
                    details=f"Чередование (пред.={self.last_speaker})"
                ))

        # Резолвим доказательства
        if self.evidence_resolver and all_evidences:
            result = self.evidence_resolver.resolve(all_evidences)
            reasoning = result.reasoning
            return result.speaker, result.confidence, reasoning

        # Fallback на простой подсчёт
        return self._simple_score_analysis(all_evidences)

    def _simple_score_analysis(self, evidences: List) -> Tuple[str, float, List[str]]:
        """Простой подсчёт баллов если резолвер недоступен"""
        scores = {'male': 0.0, 'female': 0.0}
        reasoning = []

        for ev in evidences:
            if hasattr(ev, 'gender') and ev.gender in scores:
                scores[ev.gender] += getattr(ev, 'weight', 1.0)

        total = scores['male'] + scores['female']
        if total == 0:
            return 'unknown', 0.0, ['Нет доказательств']

        if scores['male'] > scores['female']:
            conf = (scores['male'] - scores['female']) / total
            reasoning.append(f"male={scores['male']:.1f} vs female={scores['female']:.1f}")
            return 'male', conf, reasoning
        elif scores['female'] > scores['male']:
            conf = (scores['female'] - scores['male']) / total
            reasoning.append(f"female={scores['female']:.1f} vs male={scores['male']:.1f}")
            return 'female', conf, reasoning

        return 'unknown', 0.0, ['Ничья']

    def _smart_fallback(self, line: Line) -> Tuple[str, str]:
        """Умный фолбэк с использованием стратегий"""
        # Используем модуль фолбэка если доступен
        if self.fallback_strategy and self.context_manager:
            doc_stats = None
            if self.stats_fallback:
                doc_stats = self.stats_fallback.get_ratio()

            result = self.fallback_strategy.get_fallback_speaker(
                line, self.context_manager, doc_stats
            )
            if result:
                return result

        # Простой фолбэк
        text_lower = line.original.lower()
        male_verbs = len(re.findall(r'\b\S+л\b', text_lower))
        female_verbs = len(re.findall(r'\b\S+ла\b', text_lower))

        if male_verbs > female_verbs:
            return "male", f"глаголы м.р. ({male_verbs} vs {female_verbs})"
        elif female_verbs > male_verbs:
            return "female", f"глаголы ж.р. ({female_verbs} vs {male_verbs})"

        if self.last_speaker and self.last_speaker != "narrator":
            opposite = "female" if self.last_speaker == "male" else "male"
            return opposite, "чередование"

        return "male", "умолчание"

    def _log_statistics(self):
        """Логирование статистики"""
        total = self.stats['total_lines']
        dialogue = self.stats.get('dialogue_lines', 0)

        _safe_print(f"  Всего строк: {total}")
        _safe_print(f"  Диалоговых: {dialogue}")

        if dialogue > 0:
            _safe_print(f"  Определено аналитикой: {self.stats.get('resolved', 0)}")
            _safe_print(f"  Из контекста: {self.stats.get('from_context', 0)}")
            _safe_print(f"  Фолбэк: {self.stats.get('fallback', 0)}")

        speakers = {}
        if self._last_ubf:
            for line in self._last_ubf.lines:
                if line.speaker:
                    speakers[line.speaker] = speakers.get(line.speaker, 0) + 1

        if speakers:
            _safe_print(f"  Распределение спикеров: {speakers}")
