# core/pipeline/stage5_tts.py
"""
Stage 5 — Assembler
🔥 ИСПРАВЛЕН: Работает с обновлённой моделью, простой и надёжный
"""

from pathlib import Path
from typing import List
import numpy as np
import soundfile as sf

from core.models import UserBookFormat, Line


class Stage5Assembler:
    """
    Stage 5 — Assembler
    Простой и надёжный сборщик аудио
    """

    SAMPLE_RATE = 22050

    def process(self, ubf: UserBookFormat, out_file: Path) -> Path:
        """Сборка итогового аудио"""
        out_file.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n🎵 Stage 5: Сборка аудио")
        print(f"  Выходной файл: {out_file}")

        # Используем простой ассемблер
        return self._simple_assemble(ubf, out_file)

    def _simple_assemble(self, ubf: UserBookFormat, out_file: Path) -> Path:
        """Простая сборка - работает всегда"""
        audio_chunks = []

        # Сортируем линии по ID
        sorted_lines = sorted(ubf.lines, key=lambda l: l.idx)

        print(f"  Обработка {len(sorted_lines)} аудио файлов")

        for i, line in enumerate(sorted_lines, 1):
            if not line.audio_path:
                print(f"  ⚠️  Line {line.idx}: нет audio_path")
                continue

            # Находим аудио файл
            audio_path = self._find_audio_file(line)
            if not audio_path:
                print(f"  ⚠️  Line {line.idx}: файл не найден")
                continue

            try:
                # Загружаем аудио
                audio, sr = sf.read(str(audio_path), dtype='float32')

                # Ресемплируем если нужно
                if sr != self.SAMPLE_RATE:
                    if sr == 44100:
                        audio = audio[::2]
                    elif sr == 48000:
                        audio = audio[::2]
                    else:
                        # Простая интерполяция
                        ratio = sr / self.SAMPLE_RATE
                        new_len = int(len(audio) / ratio)
                        indices = np.arange(new_len) * ratio
                        audio = np.interp(indices, np.arange(len(audio)), audio)

                # Добавляем аудио
                audio_chunks.append(audio)

                # Добавляем паузу (кроме последнего)
                if i < len(sorted_lines):
                    # Пауза из эмоций или дефолтная
                    pause_ms = line.emotion.pause_after if line.emotion else 300
                    pause_samples = int(pause_ms * self.SAMPLE_RATE / 1000)

                    # Для сегментов - меньшая пауза
                    if line.is_segment and line.segment_index is not None:
                        if line.segment_index < line.segment_total - 1:
                            pause_samples = int(100 * self.SAMPLE_RATE / 1000)  # 100ms

                    if pause_samples > 0:
                        pause_audio = np.zeros(pause_samples, dtype=np.float32)
                        audio_chunks.append(pause_audio)

                # Логирование
                seg_info = ""
                if line.is_segment:
                    seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"

                print(f"    {i:3d}. Line {line.idx}{seg_info}: {len(audio) / sr:.2f}с")

            except Exception as e:
                print(f"  ❌ Line {line.idx}: ошибка - {e}")

        if not audio_chunks:
            raise RuntimeError("Нет аудио для сборки")

        # Склеиваем всё
        final_audio = np.concatenate(audio_chunks)

        # Сохраняем
        sf.write(out_file, final_audio, self.SAMPLE_RATE, subtype='PCM_16')

        # Статистика
        duration = len(final_audio) / self.SAMPLE_RATE
        size_mb = out_file.stat().st_size / 1024 / 1024

        print(f"\n✅ Stage 5 завершён:")
        print(f"   Файл: {out_file}")
        print(f"   Длительность: {duration:.2f} секунд")
        print(f"   Размер: {size_mb:.2f} MB")
        print(f"   Аудио сегментов: {len(audio_chunks)}")

        return out_file

    def _find_audio_file(self, line: Line) -> Path | None:
        """Находит аудио файл в разных местах"""
        if not line.audio_path:
            return None

        # Пробуем путь из line.audio_path
        path = Path(line.audio_path)
        if path.exists():
            return path

        # Ищем в различных директориях
        filename = Path(line.audio_path).name

        possible_locations = [
            # Основные места
            Path("storage/audio/segments/raw") / filename,
            Path("storage/audio/segments") / filename,
            Path("storage/audio/raw") / filename,
            Path("storage/audio") / filename,

            # Без суффиксов
            Path("storage/audio/segments/raw") / filename.replace("_enhanced", ""),
            Path("storage/audio/segments") / filename.replace("_enhanced", ""),

            # Для сегментов - ищем по базовому ID
            self._find_segment_file(line, filename),
        ]

        for location in possible_locations:
            if location and location.exists():
                return location

        return None

    def _find_segment_file(self, line: Line, filename: str) -> Path | None:
        """Ищет файл сегмента"""
        if not line.is_segment:
            return None

        # Пробуем разные паттерны
        base_id = line.base_line_id if line.base_line_id is not None else line.idx
        seg_index = line.segment_index or 0

        possible_patterns = [
            f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_index}.wav",
            f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_index}_enhanced.wav",
            f"{line.idx:05d}_{line.speaker or 'narrator'}_seg{seg_index}.wav",
            f"{line.idx:05d}_{line.speaker or 'narrator'}.wav",
        ]

        # Ищем в основных директориях
        search_dirs = [
            Path("storage/audio/segments/raw"),
            Path("storage/audio/segments"),
            Path("storage/audio/raw"),
        ]

        for dir_path in search_dirs:
            if dir_path.exists():
                for pattern in possible_patterns:
                    file_path = dir_path / pattern
                    if file_path.exists():
                        return file_path

        return None


class FastAssembler(Stage5Assembler):
    """Ультра-простой ассемблер"""

    def process(self, ubf: UserBookFormat, out_file: Path) -> Path:
        """Максимально простая сборка"""
        out_file.parent.mkdir(parents=True, exist_ok=True)

        print("Быстрая сборка...")

        audio_chunks = []

        for line in sorted(ubf.lines, key=lambda l: l.idx):
            if not line.audio_path:
                continue

            path = Path(line.audio_path)
            if not path.exists():
                # Пробуем найти
                for loc in ["storage/audio/segments", "storage/audio"]:
                    test_path = Path(loc) / path.name
                    if test_path.exists():
                        path = test_path
                        break

            if path.exists():
                try:
                    audio, sr = sf.read(str(path), dtype='float32')
                    if sr == 44100:
                        audio = audio[::2]
                    audio_chunks.append(audio)

                    # Минимальная пауза
                    pause = np.zeros(int(0.2 * self.SAMPLE_RATE), dtype=np.float32)
                    audio_chunks.append(pause)

                except:
                    pass

        if audio_chunks:
            final_audio = np.concatenate(audio_chunks)
            sf.write(out_file, final_audio, self.SAMPLE_RATE)
            print(f"✅ Собрано: {len(audio_chunks)} сегментов")

        return out_file