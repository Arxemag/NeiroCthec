# core/pipeline/stage4_5_enhancer.py
"""
Stage 4.5 — Упрощённый AudioEnhancer
Только базовые функции, совместимый со всеми стейджами
"""

from pathlib import Path
from typing import Dict, Optional
import numpy as np
import soundfile as sf

from core.models import UserBookFormat, Line


class SimpleAudioEnhancer:
    """
    Простой улучшатель аудио
    Без сложных зависимостей, работает всегда
    """

    SAMPLE_RATE = 22050

    def __init__(self, enable: bool = True):
        self.enable = enable
        self.cache: Dict[str, Path] = {}

    def process(self, ubf: UserBookFormat, audio_dir: Path) -> UserBookFormat:
        """Базовая обработка аудио"""
        if not self.enable:
            return ubf

        print(f"\n🎵 Stage 4.5: Базовая обработка аудио")

        # Создаём директорию для обработанных файлов
        enhanced_dir = audio_dir / "enhanced"
        enhanced_dir.mkdir(exist_ok=True)

        processed = 0

        for line in ubf.lines:
            if not line.audio_path:
                continue

            input_path = Path(line.audio_path)
            if not input_path.exists():
                continue

            try:
                # Простая обработка
                enhanced_path = self._simple_enhance(input_path, enhanced_dir, line)
                line.audio_path = str(enhanced_path)
                processed += 1

            except Exception as e:
                print(f"  ⚠️  Ошибка обработки {input_path.name}: {e}")

        print(f"✅ Обработано файлов: {processed}")
        return ubf

    def _simple_enhance(self, input_path: Path, output_dir: Path, line: Line) -> Path:
        """Простое улучшение аудио"""
        # Имя выходного файла
        output_name = input_path.stem + "_enhanced.wav"
        output_path = output_dir / output_name

        # Если уже обработан - возвращаем
        if output_path.exists():
            return output_path

        # Загружаем аудио
        audio, sr = sf.read(str(input_path), dtype='float32')

        # 1. Нормализация громкости (простая)
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.8  # -2dB headroom

        # 2. Простое сглаживание (для сегментов)
        if line.is_segment and len(audio) > 100:
            # Fade-in/out для сегментов
            fade_samples = min(50, len(audio) // 10)
            if fade_samples > 0:
                fade_in = np.linspace(0, 1, fade_samples)
                fade_out = np.linspace(1, 0, fade_samples)

                audio[:fade_samples] *= fade_in
                audio[-fade_samples:] *= fade_out

        # 3. Сохраняем
        sf.write(str(output_path), audio, sr, subtype='PCM_16')

        return output_path


# Фабричная функция
def create_enhancer(profile: str = "simple") -> SimpleAudioEnhancer:
    """Создаёт энхансер с заданным профилем"""
    return SimpleAudioEnhancer(enable=True)