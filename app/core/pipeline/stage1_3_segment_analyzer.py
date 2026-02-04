import re
from core.models import Line, Segment

REMARK_RE = re.compile(
    r'\b(?:сказал[а]?|ответил[а]?|спросил[а]?|'
    r'произнес[а]?|заметил[а]?|добавил[а]?|'
    r'прошептал[а]?|крикнул[а]?)\b',
    re.IGNORECASE
)

MAX_LEN = 182
TARGET_LEN = 100
MIN_LEN = 80


class SegmentAnalyzer:
    """
    Stage 1.3 — SegmentAnalyzer
    🔥 ФИНАЛЬНАЯ ВЕРСИЯ: ремарки не вырезаются из speech
    """

    def split(self, line: Line) -> list[Segment]:
        if line.type == "dialogue":
            return self._split_dialogue_preserve_remarks(line)
        return self._split_narration(line)

    def _split_dialogue_preserve_remarks(self, line: Line) -> list[Segment]:
        """
        Разбивает диалог, сохраняя ремарки ВНУТРИ speech сегментов
        """
        text = line.original
        segments = []
        seg_id = 0

        # Находим все ремарки
        matches = list(REMARK_RE.finditer(text))
        if not matches:
            # Если ремарок нет - один speech сегмент
            return [
                Segment(
                    id=seg_id,
                    line_id=line.id,
                    kind="speech",
                    original_text=text,
                    char_start=0,
                    char_end=len(text),
                )
            ]

        # Разбиваем текст на части: речь-ремарка-речь-ремарка-...
        last_pos = 0
        current_speech_parts = []

        for i, match in enumerate(matches):
            start, end = match.start(), match.end()

            # Текст ДО ремарки (если есть)
            if start > last_pos:
                current_speech_parts.append(text[last_pos:start])

            # 🔥 Ключевое изменение: ремарка остается частью речи
            current_speech_parts.append(text[start:end])

            # Проверяем, заканчивается ли здесь реплика (по кавычке или точке)
            next_text = text[end:] if end < len(text) else ""
            if self._is_speech_end(next_text):
                # Создаем speech сегмент с накопленными частями
                speech_text = "".join(current_speech_parts)
                segments.append(
                    Segment(
                        id=seg_id,
                        line_id=line.id,
                        kind="speech",
                        original_text=speech_text,
                        char_start=last_pos,
                        char_end=end,
                    )
                )
                seg_id += 1

                # Также создаем remark сегмент как метку
                segments.append(
                    Segment(
                        id=seg_id,
                        line_id=line.id,
                        kind="remark",
                        original_text=match.group(),
                        char_start=start,
                        char_end=end,
                    )
                )
                seg_id += 1

                current_speech_parts = []
                last_pos = end

        # Остаток текста после последней ремарки
        if last_pos < len(text) or current_speech_parts:
            remaining_text = "".join(current_speech_parts) + text[last_pos:]
            if remaining_text.strip():
                segments.append(
                    Segment(
                        id=seg_id,
                        line_id=line.id,
                        kind="speech",
                        original_text=remaining_text,
                        char_start=last_pos,
                        char_end=len(text),
                    )
                )

        return segments

    def _is_speech_end(self, text: str) -> bool:
        """Определяет, заканчивается ли реплика"""
        # Реплика заканчивается если дальше идет кавычка, точка или пустота
        if not text.strip():
            return True

        # Ищем начало следующей реплики (кавычку)
        next_quote = re.search(r'—', text)
        if next_quote and next_quote.start() < 10:  # Кавычка близко
            return True

        # Ищем конец предложения
        if re.search(r'^[.!?]', text.lstrip()):
            return True

        return False

    def _split_narration(self, line: Line) -> list[Segment]:
        text = line.original
        segments = []
        start = 0
        seg_id = 0

        while start < len(text):
            end = min(start + MAX_LEN, len(text))
            cut = None

            for i in range(start + MIN_LEN, end):
                if text[i] in ".!?":
                    cut = i + 1
                    break

            if cut is None:
                cut = end

            segments.append(
                Segment(
                    id=seg_id,
                    line_id=line.id,
                    kind="narration",
                    original_text=text[start:cut],
                    char_start=start,
                    char_end=cut,
                )
            )

            seg_id += 1
            start = cut

        return segments
