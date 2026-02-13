from core.models import Segment, TTSMeta


class TTSDirector:
    """Stage 3 — lightweight TTS metadata director."""

    def apply(self, segment: Segment):
        text = segment.original_text.lower()

        meta = TTSMeta()

        # Громкость
        if "прошептал" in text or "шепотом" in text:
            meta.volume = "whisper"
            meta.reason = "указание на шепот"

        elif "тихо сказал" in text or "сказал тихо" in text:
            meta.volume = "quiet"
            meta.reason = "указание на тихую речь"

        elif "закричал" in text or "воскликнул" in text:
            meta.volume = "loud"
            meta.emotion = "angry"
            meta.reason = "крик / восклицание"

        # Эмоции
        if "злобно" in text:
            meta.emotion = "angry"
            meta.reason = "злобно"

        elif "грустно" in text or "печально" in text:
            meta.emotion = "sad"
            meta.reason = "грусть"

        elif "с усмешкой" in text or "иронично" in text:
            meta.emotion = "irony"
            meta.reason = "ирония"

        # Командная подача (ускоренный темп)
        if "скомандовал" in text or "скомандывал" in text or "приказал" in text:
            meta.tempo = "fast"
            meta.emotion = "tension" if meta.emotion == "neutral" else meta.emotion
            meta.reason = "командная интонация"

        # Паузы
        if segment.original_text.endswith("..."):
            meta.pause_after_ms = 600
            meta.reason = (meta.reason or "") + " | многоточие"

        if segment.original_text.startswith("—"):
            meta.pause_before_ms = 200

        segment.tts_meta = meta
        return segment
