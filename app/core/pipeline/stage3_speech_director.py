import re
from core.models import Segment, SpeechMeta


class SpeechDirector:
    """
    Stage 3 — Speech Director
    Он НЕ меняет текст.
    Он говорит КАК читать.
    """

    # =========================
    # РЕМАРКИ (приоритет №1)
    # =========================

    REMARK_RULES = [
        # шёпот
        (
            re.compile(r"\b(прошептал|шёпотом|тихо сказал|едва слышно)\b", re.I),
            dict(whisper=True, volume=0.4, energy=0.6, tempo=0.85),
            "remark:whisper",
        ),

        # крик
        (
            re.compile(r"\b(крикнул|закричал|заорал|вскричал)\b", re.I),
            dict(volume=1.4, energy=1.3, pitch=0.2),
            "remark:shout",
        ),

        # усталость / бормотание
        (
            re.compile(r"\b(устало сказал|пробормотал|выдохнул)\b", re.I),
            dict(tempo=0.8, energy=0.7),
            "remark:tired",
        ),
    ]

    # =========================
    # ПУНКТУАЦИЯ
    # =========================

    EXCLAMATION_RE = re.compile(r"!+")
    QUESTION_RE = re.compile(r"\?+")
    ELLIPSIS_RE = re.compile(r"\.\.\.|…")

    # =========================
    # ENTRY POINT
    # =========================

    def apply(self, segment: Segment):
        meta = SpeechMeta(tags=[])

        text = segment.tts_text or segment.original_text

        # ---------- БАЗА ----------
        if segment.kind == "narration":
            meta.energy = 0.95
            meta.tempo = 0.95
            meta.tags.append("base:narration")
        else:
            meta.energy = 1.0
            meta.tempo = 1.0
            meta.tags.append("base:dialogue")

        # ---------- РЕМАРКИ ----------
        for pattern, params, tag in self.REMARK_RULES:
            if pattern.search(segment.original_text):
                for k, v in params.items():
                    setattr(meta, k, v)
                meta.tags.append(tag)
                meta.tags.append("source:remark")
                break  # ремарка ВСЕГДА главнее

        # ---------- ПУНКТУАЦИЯ ----------
        if self.EXCLAMATION_RE.search(text):
            meta.energy += 0.15
            meta.pitch += 0.1
            meta.tags.append("punct:exclamation")

        if self.QUESTION_RE.search(text):
            meta.pitch += 0.2
            meta.tags.append("punct:question")

        if self.ELLIPSIS_RE.search(text):
            meta.tempo -= 0.15
            meta.pause_after += 300
            meta.tags.append("punct:ellipsis")

        # ---------- УДАРЕНИЯ ----------
        if segment.stress_applied:
            meta.respect_stress = True
            meta.tags.append("stress:applied")

        # ---------- CLAMP ----------
        segment.speech_meta = self._clamp(meta)

    # =========================
    # CLAMP
    # =========================

    @staticmethod
    def _clamp(m: SpeechMeta) -> SpeechMeta:
        m.energy = max(0.5, min(m.energy, 1.5))
        m.tempo = max(0.7, min(m.tempo, 1.3))
        m.pitch = max(-0.5, min(m.pitch, 0.5))
        m.volume = max(0.3, min(m.volume, 1.5))
        m.pause_before = min(m.pause_before, 1500)
        m.pause_after = min(m.pause_after, 1500)
        return m
