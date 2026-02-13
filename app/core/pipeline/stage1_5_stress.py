from typing import List, Dict
import importlib.util
import re

from core.resources.stress_dict_ru import STRESS_DICT

# === Unicode combining acute accent ===
STRESS = "\u0301"
VOWELS = "аеёиоуыэюя"

_spec = importlib.util.find_spec("pymorphy3")
_morph = None
if _spec is not None:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()

# =========================
# Utilities
# =========================

def count_syllables(word: str) -> List[int]:
    return [i for i, ch in enumerate(word) if ch.lower() in VOWELS]


def inject_stress(word: str, syllable_index: int) -> str | None:
    vowels = count_syllables(word)
    if syllable_index < 1 or syllable_index > len(vowels):
        return None

    pos = vowels[syllable_index - 1]
    return word[:pos + 1] + STRESS + word[pos + 1:]


def lemmatize(word: str) -> str | None:
    if _morph is None:
        return None

    parsed = _morph.parse(word)
    if not parsed:
        return None
    return parsed[0].normal_form


# =========================
# Core algorithm
# =========================

def process_segment_text(text: str):
    if not text:
        return text, []

    stress_map = []
    modified = text
    offset = 0

    # простая токенизация (Stage 1.5 не обязан быть NLP-heavy)
    for match in re.finditer(r"\b[А-Яа-яЁё]+\b", text):
        word = match.group()
        lower = word.lower()

        lemma = lemmatize(lower)
        if not lemma:
            continue

        stress_syllable = STRESS_DICT.get(lemma)
        if not stress_syllable:
            continue

        stressed = inject_stress(word, stress_syllable)
        if not stressed:
            continue

        start = match.start() + offset
        end = match.end() + offset

        modified = modified[:start] + stressed + modified[end:]
        offset += len(stressed) - len(word)

        stress_map.append({
            "word": word,
            "lemma": lemma,
            "stress": stress_syllable,
            "char_start": match.start(),
            "char_end": match.end(),
            "confidence": 0.7,
        })

    if not stress_map:
        return text, []

    return modified, stress_map


# =========================
# Pipeline Stage Wrapper
# =========================

class StressPlaceholder:
    """
    Stage 1.5 — Stress Injection (LEMMA BASED)
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def apply(self, segment):
        if not self.enabled or not segment.tts_text:
            segment.stress_map = []
            segment.stress_applied = False
            return segment

        tts_text, stress_map = process_segment_text(segment.tts_text)

        segment.tts_text = tts_text
        segment.stress_map = stress_map
        segment.stress_applied = bool(stress_map)
        return segment
