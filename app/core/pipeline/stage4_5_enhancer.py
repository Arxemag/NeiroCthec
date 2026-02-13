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
                # 🔥 ИСПРАВЛЕНИЕ: Пробуем найти файл в разных местах
                input_path = self._find_audio_file(line)
                if not input_path:
                    print(f"  ⚠️  Файл не найден для line {line.idx}")
                    continue

            try:
                # 🔥 ИСПРАВЛЕНИЕ: Сохраняем с правильным именем
                enhanced_path = self._simple_enhance(input_path, enhanced_dir, line)

                # 🔥 ВАЖНО: Обновляем audio_path в модели Line
                line.audio_path = str(enhanced_path)
                processed += 1

                print(f"  ✅ Обработан: {enhanced_path.name}")

            except Exception as e:
                print(f"  ⚠️  Ошибка обработки {input_path.name}: {e}")

        print(f"✅ Обработано файлов: {processed}")
        return ubf

    def _simple_enhance(self, input_path: Path, output_dir: Path, line: Line) -> Path:
        """Простое улучшение аудио"""
        # 🔥 ИСПРАВЛЕНИЕ: Сохраняем с тем же именем файла
        if line.is_segment:
            base_id = line.base_line_id if line.base_line_id is not None else line.idx
            seg_idx = line.segment_index or 0
            output_name = f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_idx}_enhanced.wav"
        else:
            output_name = f"{line.idx:05d}_{line.speaker or 'narrator'}_enhanced.wav"

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

    def _find_audio_file(self, line: Line) -> Optional[Path]:
        """Находит аудио файл в разных местах"""
        if line.audio_path:
            path = Path(line.audio_path)
            if path.exists():
                return path

        # Ищем по паттерну имени
        if line.is_segment:
            base_id = line.base_line_id if line.base_line_id is not None else line.idx
            seg_idx = line.segment_index or 0
            patterns = [
                f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav",
                f"{line.idx:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav",
            ]
        else:
            patterns = [
                f"{line.idx:05d}_{line.speaker or 'narrator'}.wav",
            ]

        # Места для поиска
        search_dirs = [
            Path("storage/audio/segments/raw"),
            Path("storage/audio/segments"),
            Path("storage/audio/raw"),
            Path("storage/audio"),
        ]

        for dir_path in search_dirs:
            if dir_path.exists():
                for pattern in patterns:
                    file_path = dir_path / pattern
                    if file_path.exists():
                        return file_path

        return None


# Фабричная функция
def create_enhancer(profile: str = "simple") -> SimpleAudioEnhancer:
    """Создаёт энхансер с заданным профилем"""
    return SimpleAudioEnhancer(enable=True)