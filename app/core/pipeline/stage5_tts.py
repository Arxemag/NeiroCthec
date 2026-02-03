# core/pipeline/stage5_tts.py
"""
Stage 5 — Assembler
🔥 ИСПРАВЛЕН: Корректная сортировка по исходному порядку строк
"""

from pathlib import Path
from typing import List
import numpy as np
import soundfile as sf

from core.models import UserBookFormat, Line


class Stage5Assembler:
    """
    Stage 5 — Assembler
    Собирает аудио в правильном порядке
    """

    SAMPLE_RATE = 22050

    def process(self, ubf: UserBookFormat, out_file: Path) -> Path:
        """Сборка итогового аудио в правильном порядке"""
        out_file.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n🎵 Stage 5: Сборка аудио")
        print(f"  Выходной файл: {out_file}")

        return self._correct_order_assemble(ubf, out_file)

    def _correct_order_assemble(self, ubf: UserBookFormat, out_file: Path) -> Path:
        """Сборка в правильном порядке - исправляет проблему с индексами"""
        audio_chunks = []

        # 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная сортировка
        # Используем base_line_id для сегментов, чтобы восстановить исходный порядок
        sorted_lines = self._get_correctly_sorted_lines(ubf)

        print(f"  Обработка {len(sorted_lines)} аудио файлов")
        print(f"  Правильный порядок восстановлен")

        for i, (sort_key, line) in enumerate(sorted_lines, 1):
            audio_path = self._find_audio_file(line)

            if not audio_path:
                print(f"  ⚠️  Line {line.idx}: файл не найден")
                # Добавляем тишину для пропущенной строки
                silence_samples = int(0.5 * self.SAMPLE_RATE)
                silence = np.zeros(silence_samples, dtype=np.float32)
                audio_chunks.append(silence)
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

                # Логирование с информацией о порядке
                self._log_line_info(i, line, audio, sr, sort_key)

            except Exception as e:
                print(f"  ❌ Line {line.idx}: ошибка - {e}")
                # Добавляем тишину вместо пропущенного файла
                silence_samples = int(0.5 * self.SAMPLE_RATE)
                silence = np.zeros(silence_samples, dtype=np.float32)
                audio_chunks.append(silence)

        if not audio_chunks:
            raise RuntimeError("Нет аудио для сборки")

        # Склеиваем всё
        final_audio = np.concatenate(audio_chunks)

        # Сохраняем
        sf.write(out_file, final_audio, self.SAMPLE_RATE, subtype='PCM_16')

        # Статистика
        self._log_statistics(out_file, final_audio, sorted_lines)

        return out_file

    def _get_correctly_sorted_lines(self, ubf: UserBookFormat) -> List[tuple]:
        """
        🔥 ВОССТАНАВЛИВАЕТ ПРАВИЛЬНЫЙ ПОРЯДОК СТРОК
        Исправляет проблему с индексами из Stage1
        """
        lines_with_sort_key = []

        for line in ubf.lines:
            # Для сегментов используем base_line_id для правильного порядка
            if line.is_segment and line.base_line_id is not None:
                # Ключ сортировки: сначала по базовому ID, потом по индексу сегмента
                sort_key = (line.base_line_id, line.segment_index or 0)
            else:
                # Для обычных строк используем idx
                sort_key = (line.idx, 0)

            lines_with_sort_key.append((sort_key, line))

        # Сортируем по ключу
        return sorted(lines_with_sort_key, key=lambda x: x[0])

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

        # Места для поиска
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
            return audio[::2]

        if src_sr == 48000 and target_sr == 22050:
            return audio[::2]

        ratio = src_sr / target_sr
        new_len = int(len(audio) / ratio)
        indices = np.arange(new_len) * ratio
        return np.interp(indices, np.arange(len(audio)), audio)

    def _calculate_pause_samples(self, line: Line) -> int:
        """Рассчитывает длину паузы в сэмплах"""
        # Для сегментов одной реплики - минимальная пауза
        if line.is_segment and line.segment_index is not None:
            if line.segment_index < line.segment_total - 1:
                return int(50 * self.SAMPLE_RATE / 1000)  # 50ms между сегментами

        # Пауза из эмоций
        if line.emotion and line.emotion.pause_after:
            # Для диалогов больше пауза, для повествования меньше
            if line.type == "dialogue":
                return int(line.emotion.pause_after * self.SAMPLE_RATE / 1000)
            else:
                return int((line.emotion.pause_after * 0.7) * self.SAMPLE_RATE / 1000)

        # Дефолтные паузы
        if line.type == "dialogue":
            return int(400 * self.SAMPLE_RATE / 1000)  # 400ms для диалогов
        else:
            return int(200 * self.SAMPLE_RATE / 1000)  # 200ms для повествования

    def _log_line_info(self, i: int, line: Line, audio: np.ndarray, sr: int, sort_key: tuple):
        """Логирование информации о строке"""
        seg_info = ""
        if line.is_segment:
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"

        order_info = ""
        if line.is_segment:
            order_info = f" (базовый ID: {line.base_line_id})"

        duration = len(audio) / sr
        print(f"    {i:3d}. Line {line.idx}{seg_info}: {duration:.2f}с ({line.speaker}){order_info}")

    def _log_statistics(self, out_file: Path, final_audio: np.ndarray, sorted_lines: List[tuple]):
        """Логирование статистики сборки"""
        duration = len(final_audio) / self.SAMPLE_RATE
        size_mb = out_file.stat().st_size / 1024 / 1024

        # Статистика по спикерам в правильном порядке
        print(f"\n📊 Порядок спикеров в сборке:")

        speakers_in_order = []
        current_speaker = None
        speaker_count = 0

        for _, line in sorted_lines:
            if line.speaker != current_speaker:
                if current_speaker:
                    speakers_in_order.append(f"{current_speaker}(x{speaker_count})")
                current_speaker = line.speaker
                speaker_count = 1
            else:
                speaker_count += 1

        if current_speaker:
            speakers_in_order.append(f"{current_speaker}(x{speaker_count})")

        print(f"   Последовательность: {' → '.join(speakers_in_order)}")

        print(f"\n✅ Stage 5 завершён:")
        print(f"   Файл: {out_file}")
        print(f"   Длительность: {duration:.2f} секунд ({duration / 60:.2f} минут)")
        print(f"   Размер: {size_mb:.2f} MB")
        print(f"   Аудио сегментов: {len(sorted_lines)}")


class FastAssembler(Stage5Assembler):
    """Ультра-простой ассемблер с правильным порядком"""

    def process(self, ubf: UserBookFormat, out_file: Path) -> Path:
        """Максимально простая сборка с правильным порядком"""
        out_file.parent.mkdir(parents=True, exist_ok=True)

        print("Быстрая сборка с правильным порядком...")

        audio_chunks = []

        # Используем правильную сортировку
        sorted_lines = self._get_correctly_sorted_lines(ubf)

        for sort_key, line in sorted_lines:
            if not line.audio_path:
                continue

            path = Path(line.audio_path)
            if not path.exists():
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

            # Статистика по порядку
            speakers_seq = []
            current = None
            count = 0

            for _, line in sorted_lines:
                if line.speaker != current:
                    if current:
                        speakers_seq.append(f"{current}(x{count})")
                    current = line.speaker
                    count = 1
                else:
                    count += 1

            if current:
                speakers_seq.append(f"{current}(x{count})")

            duration = len(final_audio) / self.SAMPLE_RATE
            print(f"✅ Собрано: {len(audio_chunks)} сегментов, {duration:.2f} секунд")
            print(f"   Порядок: {' → '.join(speakers_seq)}")

        return out_file


# Дополнительная утилита для проверки порядка
def check_line_order(ubf: UserBookFormat):
    """Проверяет и выводит порядок строк"""
    print("\n🔍 ПРОВЕРКА ПОРЯДКА СТРОК:")
    print("=" * 60)

    assembler = Stage5Assembler()
    sorted_lines = assembler._get_correctly_sorted_lines(ubf)

    print("Исходный порядок (как в файле):")
    for i, line in enumerate(ubf.lines[:10]):  # Первые 10 строк
        seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
        print(f"  {i + 1:2d}. ID:{line.idx:5d}{seg_info}: {line.speaker} - {line.original[:50]}...")

    print("\nПравильный порядок сборки:")
    for i, (sort_key, line) in enumerate(sorted_lines[:15]):  # Первые 15 в правильном порядке
        seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
        base_info = f" (base:{line.base_line_id})" if line.base_line_id is not None else ""
        print(f"  {i + 1:2d}. Сортировка:{sort_key}{base_info}: {line.speaker} - {line.original[:40]}...")