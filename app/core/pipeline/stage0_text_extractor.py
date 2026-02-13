import xml.etree.ElementTree as ET
from core.models import NormalizedBook


class TextExtractor:
    """
    Stage 0.3 — TextExtractor
    Извлекает ЧЕЛОВЕЧЕСКИЙ текст.
    """

    def extract(self, raw_text: str, fmt: str) -> NormalizedBook:
        if fmt == "txt":
            lines = [l.rstrip() for l in raw_text.splitlines() if l.strip()]
            return NormalizedBook(
                raw_text=raw_text,
                lines=lines,
                source_format="txt",
            )

        if fmt == "fb2":
            return self._extract_fb2(raw_text)

        raise ValueError(f"No extractor for format: {fmt}")

    def _extract_fb2(self, raw_text: str) -> NormalizedBook:
        root = ET.fromstring(raw_text)

        ns = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}
        lines: list[str] = []

        # Заголовки книг / секций
        for title in root.findall(".//fb:title", ns):
            text = self._collect_text(title)
            if text:
                lines.append(text)

        # Основной текст
        for p in root.findall(".//fb:p", ns):
            text = self._collect_text(p)
            if text:
                lines.append(text)

        return NormalizedBook(
            raw_text=raw_text,
            lines=lines,
            source_format="fb2",
        )

    def _collect_text(self, elem) -> str:
        parts = []
        if elem.text:
            parts.append(elem.text)

        for child in elem:
            if child.text:
                parts.append(child.text)
            if child.tail:
                parts.append(child.tail)

        return "".join(parts).strip()
