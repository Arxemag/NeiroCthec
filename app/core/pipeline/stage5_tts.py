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
            # 🔥 ИСПРАВЛЕНИЕ: Пробуем найти файл несколькими способами
            audio_path = self._find_audio_file(line)

            if not audio_path:
                print(f"  ⚠️  Line {line.idx}: файл не найден")
                continue

            try:
                # Загружаем аудио
                audio, sr = sf.read(str(audio_path), dtype='float32')

                # Ресемплируем если нужно
                if sr != self.SAMPLE_RATE:
                    audio = self._resample_audio(audio, sr, self.SAMPLE_RATE)

                # Добавляем аудио
                audio_chunks.append(audio)

                # Добавляем паузу (кроме последнего)
                if i < len(sorted_lines):
                    pause_samples = self._calculate_pause_samples(line)
                    if pause_samples > 0:
                        pause_audio = np.zeros(pause_samples, dtype=np.float32)
                        audio_chunks.append(pause_audio)

                # Логирование
                self._log_line_info(i, line, audio, sr)

            except Exception as e:
                print(f"  ❌ Line {line.idx}: ошибка - {e}")
                # Добавляем тишину вместо пропущенного файла
                silence_samples = int(0.5 * self.SAMPLE_RATE)  # 0.5 секунды тишины
                silence = np.zeros(silence_samples, dtype=np.float32)
                audio_chunks.append(silence)

        if not audio_chunks:
            raise RuntimeError("Нет аудио для сборки")

        # Склеиваем всё
        final_audio = np.concatenate(audio_chunks)

        # Сохраняем
        sf.write(out_file, final_audio, self.SAMPLE_RATE, subtype='PCM_16')

        # Статистика
        self._log_statistics(out_file, final_audio)

        return out_file

    def _find_audio_file(self, line: Line) -> Path | None:
        """Находит аудио файл в разных местах"""
        # 1. Проверяем путь из line.audio_path
        if line.audio_path:
            path = Path(line.audio_path)
            if path.exists():
                return path

        # 2. Пробуем найти файл по различным паттернам
        if line.is_segment:
            base_id = line.base_line_id if line.base_line_id is not None else line.idx
            seg_idx = line.segment_index or 0
            patterns = [
                # Обработанные файлы (enhanced)
                f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_idx}_enhanced.wav",
                f"{line.idx:05d}_{line.speaker or 'narrator'}_seg{seg_idx}_enhanced.wav",
                # Сырые файлы (raw)
                f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav",
                f"{line.idx:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav",
            ]
        else:
            patterns = [
                # Обработанные файлы (enhanced)
                f"{line.idx:05d}_{line.speaker or 'narrator'}_enhanced.wav",
                # Сырые файлы (raw)
                f"{line.idx:05d}_{line.speaker or 'narrator'}.wav",
            ]

        # Места для поиска (в порядке приоритета)
        search_dirs = [
            Path("storage/audio/segments/enhanced"),
            Path("storage/audio/enhanced"),
            Path("storage/audio/segments/raw"),
            Path("storage/audio/raw"),
            Path("storage/audio/segments"),
            Path("storage/audio"),
        ]

        for dir_path in search_dirs:
            if dir_path.exists():
                for pattern in patterns:
                    file_path = dir_path / pattern
                    if file_path.exists():
                        return file_path

        return None

    def _resample_audio(self, audio: np.ndarray, src_sr: int, target_sr: int) -> np.ndarray:
        """Простой ресемплинг аудио"""
        if src_sr == target_sr:
            return audio

        if src_sr == 44100 and target_sr == 22050:
            return audio[::2]  # Простая децимация

        if src_sr == 48000 and target_sr == 22050:
            return audio[::2]  # Приблизительный ресемплинг

        # Простая линейная интерполяция для других случаев
        ratio = src_sr / target_sr
        new_len = int(len(audio) / ratio)
        indices = np.arange(new_len) * ratio
        return np.interp(indices, np.arange(len(audio)), audio)

    def _calculate_pause_samples(self, line: Line) -> int:
        """Рассчитывает длину паузы в сэмплах"""
        # Базовые паузы
        if line.is_segment and line.segment_index is not None:
            if line.segment_index < line.segment_total - 1:
                return int(100 * self.SAMPLE_RATE / 1000)  # 100ms между сегментами

        # Пауза из эмоций или дефолтная
        if line.emotion and line.emotion.pause_after:
            return int(line.emotion.pause_after * self.SAMPLE_RATE / 1000)

        return int(300 * self.SAMPLE_RATE / 1000)  # 300ms по умолчанию

    def _log_line_info(self, i: int, line: Line, audio: np.ndarray, sr: int):
        """Логирование информации о строке"""
        seg_info = ""
        if line.is_segment:
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"

        duration = len(audio) / sr
        print(f"    {i:3d}. Line {line.idx}{seg_info}: {duration:.2f}с ({line.speaker})")

    def _log_statistics(self, out_file: Path, final_audio: np.ndarray):
        """Логирование статистики сборки"""
        duration = len(final_audio) / self.SAMPLE_RATE
        size_mb = out_file.stat().st_size / 1024 / 1024

        print(f"\n✅ Stage 5 завершён:")
        print(f"   Файл: {out_file}")
        print(f"   Длительность: {duration:.2f} секунд ({duration / 60:.2f} минут)")
        print(f"   Размер: {size_mb:.2f} MB")


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
                # 🔥 ИСПРАВЛЕНИЕ: Ищем файл в разных местах
                path = self._find_audio_file(line)
                if not path:
                    continue

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
            duration = len(final_audio) / self.SAMPLE_RATE
            print(f"✅ Собрано: {len(audio_chunks)} сегментов, {duration:.2f} секунд")

        return out_file