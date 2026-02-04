from core.models import Segment


class StressPlaceholder:
    """
    Stage 1.5 — Заглушка для ударений
    """

    def apply(self, segment: Segment) -> Segment:
        segment.stress_map = None
        return segment
