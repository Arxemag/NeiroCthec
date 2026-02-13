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
    🔥 ИСПРАВЛЕН: Правильная индексация для сохранения порядка строк
    """

    # Оптимальные параметры для XTTS v2
    XTTS_MAX_CHARS = 160
    XTTS_OPTIMAL_MIN = 40
    XTTS_OPTIMAL_MAX = 120

    # 🔥 Множитель для индексации (оставляем место для сегментов)
    ID_MULTIPLIER = 100

    def __init__(self, split_for_xtts: bool = True):
        self.split_for_xtts = split_for_xtts
        self._next_id = 0  # 🔥 Счетчик для последовательных ID

    @staticmethod
    def _soft_clean(text: str) -> str:
        """Очистка текста без удаления полезной информации"""
        text = text.strip()
        text = re.sub(r'[\*\#@%]', '', text)
        # Сохраняем многоточия и тире
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def _normalize_sentence_endings(text: str) -> str:
        """Заменяет финальные точки на многоточия для более мягкой интонации TTS."""
        if text.endswith("..."):
            return text
        if text.endswith("…"):
            return text
        if text.endswith("."):
            return f"{text[:-1]}…"
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
        base_id = self._next_id  # 🔥 Используем текущий ID как базовый

        for i, segment in enumerate(segments):
            # Определяем тип: диалог или повествование
            line_type = "dialogue" if is_dialogue else "narrator"
            segment_is_dialogue = bool(DIALOGUE_START_RE.match(segment)) if is_dialogue else False

            # 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная индексация
            line = Line(
                idx=self._next_id,  # 🔥 Последовательный ID
                type=line_type,
                original=segment,
                remarks=self._extract_remarks(segment) if segment_is_dialogue else [],
                is_segment=True,
                segment_index=i,
                segment_total=len(segments),
                full_original=text if i == 0 else None,
                base_line_id=base_id,  # 🔥 Базовый ID для всех сегментов одной строки
                speaker=None,
                emotion=None,
                audio_path=None
            )

            lines.append(line)
            self._next_id += 1  # 🔥 Увеличиваем счетчик

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
        self._next_id = 0  # 🔥 Сбрасываем счетчик при каждом вызове

        with book_path.open("r", encoding="utf-8") as f:
            for idx, raw in enumerate(f):
                raw = raw.strip()
                if not raw:
                    continue

                original = self._soft_clean(raw)
                original = self._normalize_sentence_endings(original)
                is_dialogue = bool(DIALOGUE_START_RE.match(original))

                # Разбиваем как диалоги, так и повествование
                if self.split_for_xtts and self._should_split_for_xtts(original):
                    segment_lines = self._split_for_xtts(original, idx, is_dialogue)
                    parsed_lines.extend(segment_lines)
                else:
                    # 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная индексация
                    line = Line(
                        idx=self._next_id,  # 🔥 Последовательный ID
                        type="dialogue" if is_dialogue else "narrator",
                        original=original,
                        remarks=self._extract_remarks(original) if is_dialogue else [],
                        is_segment=False,
                        segment_index=None,
                        segment_total=None,
                        full_original=None,
                        base_line_id=self._next_id,  # 🔥 Для несмегментированных строк base_id = id
                        speaker=None,
                        emotion=None,
                        audio_path=None
                    )
                    parsed_lines.append(line)
                    self._next_id += 1  # 🔥 Увеличиваем счетчик

        # 🔥 Проверяем порядок ID
        self._validate_line_order(parsed_lines)

        print(f"✅ Stage1: Обработано {len(parsed_lines)} строк")
        if self.split_for_xtts:
            segments = [l for l in parsed_lines if l.is_segment]
            print(f"✅ Stage1: Создано {len(segments)} сегментов")

        # 🔥 Выводим информацию о порядке
        self._print_order_info(parsed_lines)

        return UserBookFormat(
            user_id=1,
            book_id=1,
            version="v1",
            lines=parsed_lines
        )

    def _validate_line_order(self, lines: List[Line]):
        """Проверяет что ID идут последовательно"""
        ids = [line.idx for line in lines]
        ids_sorted = sorted(ids)

        if ids != ids_sorted:
            print(f"⚠️  ID не отсортированы! Сортирую...")
            # Сортируем строки по ID
            lines.sort(key=lambda l: l.idx)

        # Проверяем непрерывность
        expected_ids = list(range(len(lines)))
        actual_ids = [line.idx for line in lines]

        if expected_ids != actual_ids:
            print(f"⚠️  ID не непрерывны!")
            print(f"   Ожидалось: {expected_ids[:10]}...")
            print(f"   Получено: {actual_ids[:10]}...")

            # Исправляем ID
            for i, line in enumerate(lines):
                line.idx = i
            print(f"   ✅ ID исправлены")

    def _print_order_info(self, lines: List[Line]):
        """Выводит информацию о порядке строк"""
        print("\n📊 Информация о порядке строк:")
        print("-" * 50)

        # Группируем по базовым ID для сегментов
        base_id_groups = {}
        for line in lines:
            if line.is_segment and line.base_line_id is not None:
                if line.base_line_id not in base_id_groups:
                    base_id_groups[line.base_line_id] = []
                base_id_groups[line.base_line_id].append(line)

        # Выводим первые 5 групп сегментов
        if base_id_groups:
            print(f"  Сегменты сгруппированы по {len(base_id_groups)} базовым ID")
            for i, (base_id, seg_lines) in enumerate(list(base_id_groups.items())[:3]):
                seg_ids = [l.idx for l in seg_lines]
                print(f"    Базовый ID {base_id}: сегменты {seg_ids}")

        # Выводим первые 10 строк с их порядком
        print(f"\n  Первые 10 строк в порядке сборки:")
        for i, line in enumerate(lines[:10]):
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
            base_info = f" (base:{line.base_line_id})" if line.base_line_id != line.idx else ""
            print(f"    {i:2d}. ID:{line.idx:3d}{seg_info}{base_info}: {line.type} - {line.original[:40]}...")

        # Проверяем правильность порядка для Stage5
        print(f"\n  Проверка для Stage5:")
        for i in range(min(5, len(lines) - 1)):
            current = lines[i]
            next_line = lines[i + 1]

            # Проверяем логику сортировки Stage5
            if current.is_segment and next_line.is_segment:
                if current.base_line_id == next_line.base_line_id:
                    # Сегменты одной строки должны идти подряд
                    if current.segment_index < next_line.segment_index:
                        print(f"    ✅ Сегменты {current.idx} → {next_line.idx}: правильный порядок")
                    else:
                        print(f"    ⚠️  Сегменты {current.idx} → {next_line.idx}: НЕПРАВИЛЬНЫЙ порядок!")
            else:
                print(f"    {current.idx} → {next_line.idx}: OK")


# 🔥 Дополнительная утилита для тестирования порядка
def test_line_order_simple():
    """Тестирование порядка строк на простом примере"""
    print("🧪 Тестирование порядка строк Stage1")
    print("=" * 60)

    test_content = """Первое повествование, которое достаточно длинное чтобы быть разбитым на сегменты для XTTS v2 модели синтеза речи.
— Привет, — сказал он. — Как дела?
Второе повествование покороче.
— Отлично! — ответила она."""

    test_file = Path("storage/books/test_order.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(test_content, encoding="utf-8")

    parser = StructuralParser(split_for_xtts=True)
    ubf = parser.parse_file(test_file)

    print(f"\n📋 Результат парсинга ({len(ubf.lines)} строк):")
    for i, line in enumerate(ubf.lines):
        seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
        base_info = f" (base:{line.base_line_id})" if line.base_line_id != line.idx else ""
        print(
            f"  {i:2d}. ID:{line.idx:3d}{seg_info}{base_info}: {line.type}/{line.speaker or '?'} - {line.original[:50]}...")

    # Проверяем сортировку для Stage5
    print(f"\n🔍 Проверка сортировки для Stage5:")

    # Имитируем логику Stage5
    lines_with_sort_key = []
    for line in ubf.lines:
        if line.is_segment and line.base_line_id is not None:
            sort_key = (line.base_line_id, line.segment_index or 0)
        else:
            sort_key = (line.idx, 0)
        lines_with_sort_key.append((sort_key, line))

    sorted_lines = sorted(lines_with_sort_key, key=lambda x: x[0])

    print("  Правильный порядок сборки:")
    for i, (sort_key, line) in enumerate(sorted_lines):
        seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
        print(f"    {i:2d}. Сортировка:{sort_key}: ID:{line.idx}{seg_info} - {line.type}")

    test_file.unlink()

    return ubf
