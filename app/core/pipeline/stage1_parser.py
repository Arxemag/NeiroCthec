# core/pipeline/stage1_parser.py
import re
from pathlib import Path
from typing import List, Tuple
from dataclasses import replace

from core.models import Line, Remark, UserBookFormat

# Библиотека для качественного разбиения предложений
try:
    from razdel import sentenize

    HAS_RAZDEL = True
except ImportError:
    HAS_RAZDEL = False
    print("⚠️  razdel не установлен, используем простое разбиение")

DIALOGUE_START_RE = re.compile(r"^\s*[—–−]\s*")
DASH_SPLIT_RE = re.compile(r"\s*[—–−]\s*")

REMARK_RE = re.compile(
    r'\b(?:'
    r'сказал[а]?|ответил[а]?|спросил[а]?|'
    r'доложил[а]?|прошептал[а]?|крикнул[а]?|'
    r'скомандовал[а]?|подумал[а]?|'
    r'произнёс[а]?|буркнул[а]?|'
    r'промолвил[а]?|воскликнул[а]?|'
    r'заметил[а]?|повторил[а]?|добавил[а]?'
    r')\b',
    re.IGNORECASE
)


class StructuralParser:
    """
    Stage 1 — StructuralParser с поддержкой разбиения для XTTS
    ИСПРАВЛЕН: Работает с обновлённой моделью Line
    """

    # Оптимальные параметры для XTTS v2
    XTTS_MAX_CHARS = 160
    XTTS_OPTIMAL_MIN = 40
    XTTS_OPTIMAL_MAX = 120

    def __init__(self, split_for_xtts: bool = True):
        self.split_for_xtts = split_for_xtts

    @staticmethod
    def _soft_clean(text: str) -> str:
        """Очистка текста без удаления полезной информации"""
        text = text.strip()
        text = re.sub(r'[\*\#@%]', '', text)
        # Сохраняем многоточия и тире
        text = re.sub(r'\s+', ' ', text)
        return text

    def _extract_remarks(self, text: str) -> List[Remark]:
        """Извлечение ремарок из текста"""
        remarks = []

        # Ищем паттерны: "— ... — ремарка" или "— ... — ремарка. — ..."
        patterns = [
            r'[—–−]\s*([^—–−]+?)\s*[—–−]\s*([^—–−.]+?[.!?]?)',
            r'[—–−]\s*([^—–−.]+?)\s*,\s*([^—–−.]+?[.!?]?)\s*[—–−]',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                if len(match) == 2:
                    possible_remark = match[1].strip()
                    if REMARK_RE.search(possible_remark):
                        remarks.append(Remark(text=self._soft_clean(possible_remark)))

        return remarks

    def _should_split_for_xtts(self, text: str) -> bool:
        """Определяет, нужно ли разбивать текст для XTTS"""
        if not self.split_for_xtts:
            return False
        return len(text) > self.XTTS_OPTIMAL_MAX

    def _split_for_xtts(self, text: str, line_idx: int, is_dialogue: bool = False) -> List[Line]:
        """Разбивает текст на оптимальные сегменты для XTTS"""
        # 1. Сначала разбиваем на предложения
        sentences = self._split_into_sentences(text)

        # 2. Оптимизируем для XTTS
        segments = self._optimize_segments(sentences)

        # 3. Создаем Line для каждого сегмента
        lines = []
        for i, segment in enumerate(segments):
            # Определяем тип: диалог или повествование
            line_type = "dialogue" if is_dialogue else "narrator"
            segment_is_dialogue = bool(DIALOGUE_START_RE.match(segment)) if is_dialogue else False

            # 🔥 ИСПРАВЛЕНО: Создаём Line со всеми полями сразу
            line = Line(
                idx=line_idx * 1000 + i,
                type=line_type,
                original=segment,
                remarks=self._extract_remarks(segment) if segment_is_dialogue else [],
                is_segment=True,
                segment_index=i,
                segment_total=len(segments),
                full_original=text if i == 0 else None,
                base_line_id=line_idx,
                speaker=None,
                emotion=None,
                audio_path=None
            )

            lines.append(line)

        return lines

    def _split_into_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения"""
        if HAS_RAZDEL:
            return [sentence.text for sentence in sentenize(text) if sentence.text.strip()]
        else:
            sentences = []
            current = ""

            for char in text:
                current += char
                if char in '.!?…':
                    sentences.append(current.strip())
                    current = ""

            if current.strip():
                sentences.append(current.strip())

            return sentences

    def _optimize_segments(self, sentences: List[str]) -> List[str]:
        """Оптимизирует предложения для XTTS"""
        segments = []
        current = ""

        for sentence in sentences:
            # Пропускаем очень короткие
            if len(sentence) < 15 and sentence.endswith(('!', '?', '.')):
                if current:
                    current = f"{current} {sentence}"
                else:
                    current = sentence
                continue

            # Проверяем длину
            potential = f"{current} {sentence}".strip() if current else sentence

            if self.XTTS_OPTIMAL_MIN <= len(potential) <= self.XTTS_OPTIMAL_MAX:
                segments.append(potential)
                current = ""
            elif len(potential) < self.XTTS_OPTIMAL_MIN:
                current = potential
            else:
                if current:
                    segments.append(current)

                if len(sentence) > self.XTTS_MAX_CHARS:
                    subparts = self._split_long_sentence(sentence)
                    segments.extend(subparts[:-1])
                    current = subparts[-1] if subparts else ""
                else:
                    current = sentence

        # Обрабатываем остаток
        if current:
            if len(current) < self.XTTS_OPTIMAL_MIN and segments:
                segments[-1] = f"{segments[-1]} {current}"
            else:
                segments.append(current)

        return segments

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """Разбивает длинное предложение"""
        # Разбиваем по союзам и запятым
        patterns = [
            r'\s+и\s+',
            r'\s+а\s+',
            r'\s+но\s+',
            r'\s+что\s+',
            r',\s+(?![0-9])',
        ]

        parts = [sentence]

        for pattern in patterns:
            new_parts = []
            for part in parts:
                if len(part) <= self.XTTS_MAX_CHARS:
                    new_parts.append(part)
                else:
                    subparts = re.split(pattern, part)
                    new_parts.extend([p for p in subparts if p])
            parts = new_parts

        # Если все еще слишком длинные
        final_parts = []
        for part in parts:
            if len(part) <= self.XTTS_MAX_CHARS:
                final_parts.append(part)
            else:
                space_pos = part.rfind(' ', self.XTTS_OPTIMAL_MIN, self.XTTS_OPTIMAL_MAX)
                if space_pos == -1:
                    space_pos = part.find(' ', self.XTTS_OPTIMAL_MAX)

                if space_pos != -1:
                    final_parts.append(part[:space_pos].strip())
                    final_parts.append(part[space_pos:].strip())
                else:
                    mid = len(part) // 2
                    final_parts.append(part[:mid].strip())
                    final_parts.append(part[mid:].strip())

        return final_parts

    def parse_file(self, book_path: Path) -> UserBookFormat:
        """Парсинг файла с поддержкой сегментов"""
        parsed_lines: List[Line] = []

        with book_path.open("r", encoding="utf-8") as f:
            for idx, raw in enumerate(f):
                raw = raw.strip()
                if not raw:
                    continue

                original = self._soft_clean(raw)
                is_dialogue = bool(DIALOGUE_START_RE.match(original))

                # 🔥 ИСПРАВЛЕНИЕ: Разбиваем как диалоги, так и повествование
                if self.split_for_xtts and self._should_split_for_xtts(original):
                    segment_lines = self._split_for_xtts(original, idx, is_dialogue)
                    parsed_lines.extend(segment_lines)
                else:
                    line = Line(
                        idx=idx,
                        type="dialogue" if is_dialogue else "narrator",
                        original=original,
                        remarks=self._extract_remarks(original) if is_dialogue else [],
                        is_segment=False,
                        segment_index=None,
                        segment_total=None,
                        full_original=None,
                        base_line_id=idx,
                        speaker=None,
                        emotion=None,
                        audio_path=None
                    )
                    parsed_lines.append(line)

        print(f"✅ Stage1: Обработано {len(parsed_lines)} строк")
        if self.split_for_xtts:
            segments = [l for l in parsed_lines if l.is_segment]
            print(f"✅ Stage1: Создано {len(segments)} сегментов")

        return UserBookFormat(
            user_id=1,
            book_id=1,
            version="v1",
            lines=parsed_lines
        )