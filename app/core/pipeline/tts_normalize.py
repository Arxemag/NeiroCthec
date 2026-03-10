"""
Нормализация текста перед отправкой в TTS (XTTS2 и др.).
Один источник правды: используется в пайплайне и при записи в storage.
"""

import re

# Символы кавычек, которые убираем перед отправкой в TTS (чтобы не озвучивались)
QUOTE_CHARS = "\"\"\"'''''\u00ab\u00bb\u201e\u201c\u2018\u2033\u2032\u2033\u300c\u300d\u301f\u00b4`"


def normalize_text_for_tts(text: str) -> str:
    """
    Нормализация текста перед отправкой в TTS.
    - Удаление кавычек.
    - Каждая строка заканчивается тремя точками (...).
    - Точка с пробелом -> три точки с пробелом; тире унифицируются.
    """
    if not text or not text.strip():
        return text.strip()
    t = text.strip()
    for q in QUOTE_CHARS:
        t = t.replace(q, "")
    lines = t.split("\n")
    normalized_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            normalized_lines.append("")
            continue
        if line.endswith("..."):
            pass
        elif line.endswith(".") and len(line) > 1:
            line = line[:-1] + "..."
        else:
            line = line.rstrip() + "..."
        # Заменяем одиночные ". " на "... " без бесконечного расширения.
        line = re.sub(r"(?<!\.)\.(?!\.)\s+", "... ", line)
        for dash in ("\u2014", "\u2013", "\u2012"):
            line = line.replace(dash, " - ")
        while "  " in line:
            line = line.replace("  ", " ")
        normalized_lines.append(line.strip())
    t = "\n".join(normalized_lines)
    while "  " in t:
        t = t.replace("  ", " ")
    return t.strip()
