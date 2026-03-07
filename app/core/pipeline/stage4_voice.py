# Coqui TTS удалён. TTS только через Qwen3 (tts_engine_service + stage4 worker).
# Заглушка, чтобы старый код не падал с ModuleNotFoundError, а получал явную ошибку.

_COQUI_REMOVED_MSG = (
    "Coqui TTS удалён. Используйте Qwen3: divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit "
    "через tts_engine_service и stage4 worker (озвучка книг)."
)


class VoiceSynthesizer:
    """Заглушка: Coqui TTS больше не используется."""

    def __init__(self, device: str = "auto"):
        raise RuntimeError(_COQUI_REMOVED_MSG)


class FastVoiceSynthesizer(VoiceSynthesizer):
    """Заглушка: Coqui TTS больше не используется."""

    def __init__(self, device: str = "auto", cache_enabled: bool = True):
        raise RuntimeError(_COQUI_REMOVED_MSG)
