# core/pipeline/stage1_parser.py
import os
import re
import sys
import builtins
from pathlib import Path
from typing import List, Tuple
from dataclasses import replace

from core.models import Line, Remark, UserBookFormat


def _safe_str(s: str, maxlen: int = 200) -> str:
    """Return string safe for Windows console (charmap): replace non-encodable chars."""
    if not s:
        return ""
    s = s[:maxlen]
    try:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        s.encode(enc)
        return s
    except UnicodeEncodeError:
        return s.encode("ascii", errors="replace").decode("ascii")


def _safe_print(*args, **kwargs):
    """Print wrapper that ignores ValueError: I/O operation on closed file (Windows console quirks)."""
    try:
        builtins.print(*args, **kwargs)
    except ValueError:
        # Если stdout/stderr уже закрыт (например, при остановке сервера) — просто игнорируем вывод
        pass

# Библиотека для качественного разбиения предложений
try:
    from razdel import sentenize

    HAS_RAZDEL = True
except ImportError:
    HAS_RAZDEL = False
    _safe_print("[!] razdel не установлен, используем простое разбиение")

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

# Заголовки глав: «Глава N», «Chapter N» (строгие строки + допускаем заголовок после номера)
CHAPTER_HEADER_RE = re.compile(
    r'^\s*(?:'
    r'Глава\s+\d+.*|'
    r'Chapter\s+\d+.*|'
    r'Глава\s+[IVXLCDM]+.*|'
    r'Chapter\s+[IVXLCDM]+.*'
    r')\s*$',
    re.IGNORECASE
)

CHAPTER_INLINE_RE = re.compile(
    r'\b(?:Глава|Chapter)\s+(?:\d+|[IVXLCDM]+)\b',
    re.IGNORECASE
)

# Метаданные/секции книги, которые должны быть отдельной строкой (не глава)
BOOK_META_HEADER_RE = re.compile(
    r'^\s*(?:'
    r'#\s*.*|'
    r'Посмертие[-–—]?\s*\d+.*|'
    r'Альфа.*|'
    r'Часть\s+(?:первая|вторая|третья|четвертая|четвёртая|пятая|шестая|седьмая|восьмая|девятая|десятая)\b.*|'
    r'Пролог\b.*|'
    r'Эпилог\b.*'
    r')\s*$',
    re.IGNORECASE
)


class StructuralParser:
    """
    Stage 1 — StructuralParser с поддержкой разбиения для XTTS
    🔥 ИСПРАВЛЕН: Правильная индексация для сохранения порядка строк
    """

    # Оптимальные параметры для XTTS v2 (fallback если env не заданы)
    XTTS_MAX_CHARS = 160
    XTTS_OPTIMAL_MIN = 40
    XTTS_OPTIMAL_MAX = 120

    # 🔥 Множитель для индексации (оставляем место для сегментов)
    ID_MULTIPLIER = 100

    def __init__(self, split_for_xtts: bool = True):
        self.split_for_xtts = split_for_xtts
        self._next_id = 0  # 🔥 Счетчик для последовательных ID
        # Env-параметры чанков (Qwen3: 200/400/600, XTTS: 40/120/160)
        self._optimal_min = int(os.getenv("TTS_CHUNK_MIN", "200"))
        self._optimal_max = int(os.getenv("TTS_CHUNK_MAX", "400"))
        self._max_chars = int(os.getenv("TTS_CHUNK_MAX_HARD", "600"))

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
        return len(text) > self._optimal_max

    def _split_for_xtts(
        self, text: str, line_idx: int, is_dialogue: bool = False, chapter_id: int = 1, is_chapter_header: bool = False
    ) -> List[Line]:
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
                chapter_id=chapter_id,
                is_chapter_header=is_chapter_header and (i == 0),  # только первый сегмент
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
        """Оптимизирует предложения для XTTS. Диалоги (—) никогда не объединяются."""
        segments = []
        current = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Диалог (начинается с —): всегда отдельный сегмент, не объединяем
            if DIALOGUE_START_RE.match(sentence):
                if current:
                    segments.append(current.strip())
                    current = ""
                segments.append(sentence)
                continue

            # Пропускаем очень короткие (только для narrator — диалоги уже обработаны)
            if len(sentence) < 15 and sentence.endswith(('!', '?', '.')):
                if current:
                    current = f"{current} {sentence}"
                else:
                    current = sentence
                continue

            # Проверяем длину
            potential = f"{current} {sentence}".strip() if current else sentence

            if self._optimal_min <= len(potential) <= self._optimal_max:
                segments.append(potential)
                current = ""
            elif len(potential) < self._optimal_min:
                current = potential
            else:
                if current:
                    segments.append(current)

                if len(sentence) > self._max_chars:
                    subparts = self._split_long_sentence(sentence)
                    segments.extend(subparts[:-1])
                    current = subparts[-1] if subparts else ""
                else:
                    current = sentence

        # Обрабатываем остаток
        if current:
            if len(current) < self._optimal_min and segments:
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
                if len(part) <= self._max_chars:
                    new_parts.append(part)
                else:
                    subparts = re.split(pattern, part)
                    new_parts.extend([p for p in subparts if p])
            parts = new_parts

        # Если все еще слишком длинные
        final_parts = []
        for part in parts:
            if len(part) <= self._max_chars:
                final_parts.append(part)
            else:
                space_pos = part.rfind(' ', self._optimal_min, self._optimal_max)
                if space_pos == -1:
                    space_pos = part.find(' ', self._optimal_max)

                if space_pos != -1:
                    final_parts.append(part[:space_pos].strip())
                    final_parts.append(part[space_pos:].strip())
                else:
                    mid = len(part) // 2
                    final_parts.append(part[:mid].strip())
                    final_parts.append(part[mid:].strip())

        return final_parts

    def _parse_chapter_id(self, header: str) -> int | None:
        """Пытается извлечь номер главы из заголовка (arabic/roman)."""
        m = re.search(r'\b(?:Глава|Chapter)\s+(\d+)\b', header, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
        m = re.search(r'\b(?:Глава|Chapter)\s+([IVXLCDM]+)\b', header, re.IGNORECASE)
        if m:
            roman = m.group(1).upper()
            roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
            total = 0
            prev = 0
            for ch in reversed(roman):
                val = roman_map.get(ch, 0)
                if val < prev:
                    total -= val
                else:
                    total += val
                    prev = val
            return total if total > 0 else None
        return None

    def _split_compound_header_line(self, text: str) -> list[str]:
        """
        Разделяет строки вида:
        "Посмертие-6... Альфа... Часть вторая Глава 1 Возмездие Перед глазами..."
        на отдельные логические строки:
        1) "Посмертие-6... Альфа... Часть вторая"
        2) "Глава 1 Возмездие"
        3) "Перед глазами..."
        """
        t = (text or "").strip()
        if not t:
            return []
        m = CHAPTER_INLINE_RE.search(t)
        if not m:
            return [t]
        before = t[:m.start()].strip()
        after = t[m.start():].strip()
        parts: list[str] = []
        if before:
            parts.append(before)
        if not after:
            return parts
        # after начинается с "Глава N ..." — отделяем заголовок от основного текста
        words = after.split()
        if len(words) <= 2:
            parts.append(after)
            return parts
        # Ищем позицию после "Глава N"
        try:
            idx = 0
            if re.fullmatch(r'(Глава|Chapter)', words[idx], re.IGNORECASE):
                idx += 1
            if idx < len(words) and re.fullmatch(r'(\d+|[IVXLCDM]+)', words[idx], re.IGNORECASE):
                idx += 1
        except Exception:
            idx = 0
        # Всё что после номера: title + body
        tail = words[idx:]
        if len(tail) <= 2:
            parts.append(after)
            return parts
        # Заголовок: первые 2 слова после номера, остальное — текст главы
        title_words = tail[:2]
        body_words = tail[2:]
        header = " ".join(words[:idx] + title_words).strip()
        body = " ".join(body_words).strip()
        if header:
            parts.append(header)
        if body:
            parts.append(body)
        return parts

    def parse_file(self, book_path: Path) -> UserBookFormat:
        """Парсинг файла с поддержкой сегментов и разметки глав по заголовкам."""
        parsed_lines: List[Line] = []
        self._next_id = 0  # 🔥 Сбрасываем счетчик при каждом вызове
        current_chapter = 1

        with book_path.open("r", encoding="utf-8") as f:
            for idx, raw in enumerate(f):
                raw = raw.strip()
                if not raw:
                    continue

                original = self._soft_clean(raw)
                for logical in self._split_compound_header_line(original):
                    logical = (logical or "").strip()
                    if not logical:
                        continue
                    is_chapter_header = bool(CHAPTER_HEADER_RE.match(logical))
                    is_meta_header = bool(BOOK_META_HEADER_RE.match(logical))
                    # Заголовок главы относится к новой главе, а не к предыдущей
                    if is_chapter_header:
                        parsed_ch = self._parse_chapter_id(logical)
                        if parsed_ch is not None:
                            current_chapter = parsed_ch
                        else:
                            current_chapter += 1
                        chapter_id = current_chapter
                    else:
                        chapter_id = current_chapter

                    is_dialogue = bool(DIALOGUE_START_RE.match(logical))

                    # Разбиваем как диалоги, так и повествование
                    if self.split_for_xtts and self._should_split_for_xtts(logical):
                        segment_lines = self._split_for_xtts(
                            logical, idx, is_dialogue, chapter_id=chapter_id, is_chapter_header=is_chapter_header
                        )
                        parsed_lines.extend(segment_lines)
                    else:
                        # 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная индексация
                        line = Line(
                            idx=self._next_id,  # 🔥 Последовательный ID
                            type="dialogue" if is_dialogue else "narrator",
                            original=logical,
                            remarks=self._extract_remarks(logical) if is_dialogue else [],
                            is_segment=False,
                            segment_index=None,
                            segment_total=None,
                            full_original=None,
                            base_line_id=self._next_id,  # 🔥 Для несмегментированных строк base_id = id
                            chapter_id=chapter_id,
                            is_chapter_header=is_chapter_header or is_meta_header,
                            speaker=None,
                            emotion=None,
                            audio_path=None
                        )
                        parsed_lines.append(line)
                        self._next_id += 1  # 🔥 Увеличиваем счетчик

        # 🔥 Проверяем порядок ID
        self._validate_line_order(parsed_lines)

        _safe_print(f"[OK] Stage1: Обработано {len(parsed_lines)} строк")
        if self.split_for_xtts:
            segments = [l for l in parsed_lines if l.is_segment]
            _safe_print(f"[OK] Stage1: Создано {len(segments)} сегментов")

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
            _safe_print(f"[!] ID не отсортированы! Сортирую...")
            # Сортируем строки по ID
            lines.sort(key=lambda l: l.idx)

        # Проверяем непрерывность
        expected_ids = list(range(len(lines)))
        actual_ids = [line.idx for line in lines]

        if expected_ids != actual_ids:
            _safe_print(f"[!] ID не непрерывны!")
            _safe_print(f"   Ожидалось: {expected_ids[:10]}...")
            _safe_print(f"   Получено: {actual_ids[:10]}...")

            # Исправляем ID
            for i, line in enumerate(lines):
                line.idx = i
            _safe_print(f"   [OK] ID исправлены")

    def _print_order_info(self, lines: List[Line]):
        """Выводит информацию о порядке строк"""
        _safe_print("\n[info] Информация о порядке строк:")
        _safe_print("-" * 50)

        # Группируем по базовым ID для сегментов
        base_id_groups = {}
        for line in lines:
            if line.is_segment and line.base_line_id is not None:
                if line.base_line_id not in base_id_groups:
                    base_id_groups[line.base_line_id] = []
                base_id_groups[line.base_line_id].append(line)

        # Выводим первые 5 групп сегментов
        if base_id_groups:
            _safe_print(f"  Сегменты сгруппированы по {len(base_id_groups)} базовым ID")
            for i, (base_id, seg_lines) in enumerate(list(base_id_groups.items())[:3]):
                seg_ids = [l.idx for l in seg_lines]
                _safe_print(f"    Базовый ID {base_id}: сегменты {seg_ids}")

        # Выводим первые 10 строк с их порядком
        _safe_print(f"\n  Первые 10 строк в порядке сборки:")
        for i, line in enumerate(lines[:10]):
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
            base_info = f" (base:{line.base_line_id})" if line.base_line_id != line.idx else ""
            _safe_print(f"    {i:2d}. ID:{line.idx:3d}{seg_info}{base_info}: {line.type} - {_safe_str(line.original, 40)}...")

        # Проверяем правильность порядка для Stage5
        _safe_print(f"\n  Проверка для Stage5:")
        for i in range(min(5, len(lines) - 1)):
            current = lines[i]
            next_line = lines[i + 1]

            # Проверяем логику сортировки Stage5
            if current.is_segment and next_line.is_segment:
                if current.base_line_id == next_line.base_line_id:
                    # Сегменты одной строки должны идти подряд
                    if current.segment_index < next_line.segment_index:
                        _safe_print(f"    [OK] Сегменты {current.idx} -> {next_line.idx}: правильный порядок")
                    else:
                        _safe_print(f"    [!] Сегменты {current.idx} -> {next_line.idx}: НЕПРАВИЛЬНЫЙ порядок!")
            else:
                _safe_print(f"    {current.idx} -> {next_line.idx}: OK")


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
