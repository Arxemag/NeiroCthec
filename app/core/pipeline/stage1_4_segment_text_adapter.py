from core.models import Segment


class SegmentTextAdapter:
    """
    Stage 1.4 — SegmentTextAdapter
    Управляет пунктуацией для TTS.
    """

    def adapt(self, segment: Segment, is_last: bool) -> Segment:
        text = segment.original_text.rstrip()

        if segment.kind == "remark":
            segment.tts_text = text
            return segment

        if text.endswith("."):
            text = text[:-1] + "…"
        elif is_last:
            text += "…"

        segment.tts_text = text
        return segment
