# debug_pipeline.py
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from core.pipeline.stage1_parser import StructuralParser
from core.pipeline.stage2_speaker import SpeakerResolver
from core.pipeline.stage3_emotion import EmotionResolver
from core.pipeline.stage4_synthesizer import VoiceSynthesizer
# Временно отключаем Stage 4.5 для отладки
# from core.pipeline.stage4_5_enhancer import create_enhancer
from core.pipeline.stage5_tts import Stage5Assembler


def run_pipeline():
    """Основной пайплайн без сложностей"""
    print("=" * 60)
    print("🚀 ОТЛАДОЧНЫЙ ПАЙПЛАЙН")
    print("=" * 60)

    # Файл книги
    book = Path("storage/books/book.txt")
    if not book.exists():
        print(f"❌ Файл книги не найден: {book}")
        return

    print(f"📖 Книга: {book}")

    # ========== STAGE 1 ==========
    print("\n" + "=" * 40)
    print("STAGE 1: ПАРСИНГ")
    print("=" * 40)

    parser = StructuralParser(split_for_xtts=True)
    ubf = parser.parse_file(book)

    print(f"✅ Обработано строк: {len(ubf.lines)}")

    # Статистика по типам
    dialogue_count = sum(1 for l in ubf.lines if l.type == "dialogue")
    narrator_count = sum(1 for l in ubf.lines if l.type == "narrator")
    segment_count = sum(1 for l in ubf.lines if l.is_segment)

    print(f"  Диалоги: {dialogue_count}")
    print(f"  Повествование: {narrator_count}")
    print(f"  Сегменты: {segment_count}")

    # Примеры первых строк
    print("\n  Примеры строк:")
    for i, line in enumerate(ubf.lines[:3]):
        seg_info = ""
        if line.is_segment:
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"
        print(f"    {i + 1}. ID:{line.idx}{seg_info}: {line.original[:60]}...")

    # ========== STAGE 2 ==========
    print("\n" + "=" * 40)
    print("STAGE 2: ОПРЕДЕЛЕНИЕ СПИКЕРОВ")
    print("=" * 40)

    resolver = SpeakerResolver()
    ubf = resolver.process(ubf)

    # Статистика спикеров
    from collections import Counter
    speakers = Counter([l.speaker for l in ubf.lines if l.speaker])
    print(f"✅ Спикеры определены:")
    for speaker, count in speakers.items():
        print(f"  {speaker}: {count}")

    # Проверяем правильность определения
    print("\n  Проверка определения:")
    for line in ubf.lines[:5]:
        if line.type == "dialogue":
            seg_info = ""
            if line.is_segment:
                seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"
            print(f"    Line {line.idx}{seg_info}: {line.speaker}")
            if line.remarks:
                print(f"      Ремарки: {[r.text for r in line.remarks]}")

    # ========== STAGE 3 ==========
    print("\n" + "=" * 40)
    print("STAGE 3: ЭМОЦИИ")
    print("=" * 40)

    emotion_resolver = EmotionResolver()
    ubf = emotion_resolver.process(ubf)

    print("✅ Эмоции определены")

    # Пример эмоций
    if ubf.lines[0].emotion:
        e = ubf.lines[0].emotion
        print(f"  Первая строка:")
        print(f"    Энергия: {e.energy:.2f}")
        print(f"    Темп: {e.tempo:.2f}")
        print(f"    Пауза до: {e.pause_before}ms")
        print(f"    Пауза после: {e.pause_after}ms")

    # ========== STAGE 4 ==========
    print("\n" + "=" * 40)
    print("STAGE 4: СИНТЕЗ РЕЧИ")
    print("=" * 40)

    # Создаём директории
    audio_dir = Path("storage/audio")
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Очищаем старые файлы
    for wav_file in audio_dir.glob("*.wav"):
        wav_file.unlink()

    synthesizer = VoiceSynthesizer()

    try:
        synthesizer.process(ubf, out_dir=audio_dir)

        # Проверяем созданные файлы
        wav_files = list(audio_dir.glob("*.wav"))
        print(f"✅ Синтез завершён")
        print(f"  Создано файлов: {len(wav_files)}")

        if wav_files:
            print("  Примеры файлов:")
            for file in wav_files[:3]:
                print(f"    {file.name}")

        # Проверяем что у всех строк есть audio_path
        lines_with_audio = [l for l in ubf.lines if l.audio_path]
        print(f"  Строк с audio_path: {len(lines_with_audio)}/{len(ubf.lines)}")

    except Exception as e:
        print(f"❌ Ошибка синтеза: {e}")
        import traceback
        traceback.print_exc()

        # Создаём заглушки для теста
        print("\n⚠️  Создаю тестовые audio_path...")
        for line in ubf.lines:
            if line.is_segment:
                seg_idx = line.segment_index or 0
                line.audio_path = f"storage/audio/{line.idx:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav"
            else:
                line.audio_path = f"storage/audio/{line.idx:05d}_{line.speaker or 'narrator'}.wav"

    # ========== STAGE 5 ==========
    print("\n" + "=" * 40)
    print("STAGE 5: СБОРКА АУДИО")
    print("=" * 40)

    final_path = Path("storage/audio/final.wav")
    final_path.parent.mkdir(parents=True, exist_ok=True)

    # Очищаем старый файл
    if final_path.exists():
        final_path.unlink()

    assembler = Stage5Assembler()

    try:
        assembler.process(ubf, final_path)

        if final_path.exists():
            # Получаем информацию о файле
            import soundfile as sf
            audio, sr = sf.read(final_path)
            duration = len(audio) / sr
            size_mb = final_path.stat().st_size / 1024 / 1024

            print(f"✅ Сборка завершена!")
            print(f"  Файл: {final_path}")
            print(f"  Длительность: {duration:.2f} секунд")
            print(f"  Размер: {size_mb:.2f} MB")
        else:
            print("❌ Финальный файл не создан")

    except Exception as e:
        print(f"❌ Ошибка сборки: {e}")
        import traceback
        traceback.print_exc()

    # ========== ИТОГ ==========
    print("\n" + "=" * 60)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)

    print(f"Всего строк: {len(ubf.lines)}")
    print(f"Диалоги: {dialogue_count}")
    print(f"Повествование: {narrator_count}")
    print(f"Сегменты: {segment_count}")

    if final_path.exists():
        print(f"\n✅ ПАЙПЛАЙН УСПЕШНО ЗАВЕРШЁН!")
        print(f"Аудиокнига сохранена: {final_path}")
    else:
        print(f"\n⚠️  ПАЙПЛАЙН ЗАВЕРШЁН С ОШИБКАМИ")

    return ubf


def test_specific_line():
    """Тест конкретной строки"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ КОНКРЕТНОЙ СТРОКИ")
    print("=" * 60)

    test_text = "— Недалеко чёрный единорог. Он как раз в списке приоритетных «покупок», — доложила она. — Он смертельно ранен, так что мы только окажем ему услугу."

    # Сохраняем в файл
    test_file = Path("storage/books/test.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(test_text, encoding="utf-8")

    # Запускаем Stage 1
    parser = StructuralParser(split_for_xtts=True)
    ubf = parser.parse_file(test_file)

    print(f"✅ Stage 1: создано {len(ubf.lines)} строк")

    for line in ubf.lines:
        seg_info = ""
        if line.is_segment:
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"
        print(f"  Line {line.idx}{seg_info}:")
        print(f"    Текст: {line.original}")
        print(f"    Тип: {line.type}")
        print(f"    Ремарки: {[r.text for r in line.remarks]}")

    # Stage 2
    resolver = SpeakerResolver()
    ubf = resolver.process(ubf)

    print(f"\n✅ Stage 2: спикеры определены")
    for line in ubf.lines:
        print(f"  Line {line.idx}: {line.speaker}")

    # Удаляем тестовый файл
    test_file.unlink()

    return ubf


if __name__ == "__main__":
    try:
        print("Начинаю отладку пайплайна...\n")

        # Запускаем основной пайплайн
        ubf = run_pipeline()

        # Дополнительный тест (раскомментируйте если нужно)
        # test_specific_line()

        print("\n" + "=" * 60)
        print("🎉 ОТЛАДКА ЗАВЕРШЕНА")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)