# Coqui XTTS-v2 больше не используется.
# TTS только через Qwen3: divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit.
# Модель подгружается в tts_engine_service при первом запросе.

if __name__ == "__main__":
    print("Coqui TTS удалён. Для TTS используется Qwen3 (tts_engine_service).")
    print("Модель: divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit")
