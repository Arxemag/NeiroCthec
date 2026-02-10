# debug_pipeline.py
from pathlib import Path
import sys
import time
import torch

sys.path.append(str(Path(__file__).parent.parent))

from app.core.pipeline.old_stage.stage1_parser import StructuralParser
from app.core.pipeline.old_stage.stage2_speaker import SpeakerResolver
from core.pipeline.stage3_speech_director import EmotionResolver
from core.pipeline.stage4_voice import VoiceSynthesizer
# Добавляем Stage 4.5 обратно
from core.pipeline.stage4_5_enhancer import create_enhancer
from core.pipeline.stage5_tts import Stage5Assembler


def check_cuda_environment():
    """Проверяет доступность CUDA в Docker"""
    print("=" * 60)
    print("🔍 ПРОВЕРКА CUDA В DOCKER")
    print("=" * 60)

    print(f"PyTorch версия: {torch.__version__}")
    print(f"CUDA доступна: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"✅ CUDA работает в Docker!")
        print(f"   CUDA версия: {torch.version.cuda}")
        print(f"   Количество GPU: {torch.cuda.device_count()}")
        print(f"   Текущий GPU: {torch.cuda.current_device()}")
        print(f"   Имя GPU: {torch.cuda.get_device_name(0)}")
        memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
        print(f"   Память GPU: {memory_gb:.1f} GB")

        # Проверяем память
        allocated = torch.cuda.memory_allocated(0) / 1024 ** 2
        reserved = torch.cuda.memory_reserved(0) / 1024 ** 2
        print(f"   Выделено памяти: {allocated:.1f} MB")
        print(f"   Зарезервировано: {reserved:.1f} MB")
    else:
        print("❌ CUDA не доступна в Docker!")
        print("   Запускайте с: docker-compose run --gpus all tts")
        print("   Или добавьте в docker-compose.yml:")
        print("   ")
        print("   deploy:")
        print("     resources:")
        print("       reservations:")
        print("         devices:")
        print("           - driver: nvidia")
        print("             count: 1")
        print("             capabilities: [gpu]")

    print("=" * 60)
    return torch.cuda.is_available()


def debug_stage_4_detailed(ubf, audio_dir):
    """Детальная отладка Stage 4 - тестирует синтез на нескольких строках"""
    print("\n" + "=" * 60)
    print("🔍 ДЕТАЛЬНАЯ ОТЛАДКА STAGE 4")
    print("=" * 60)

    # Создаём директории
    test_dir = audio_dir / "debug_test"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Выбираем 3 тестовые строки разных типов
    test_lines = []

    # Первая строка - повествование
    narrator_lines = [l for l in ubf.lines if l.type == "narrator" and not l.is_segment]
    if narrator_lines:
        test_lines.append(narrator_lines[0])

    # Вторая строка - мужской диалог
    male_lines = [l for l in ubf.lines if l.type == "dialogue" and l.speaker == "male"]
    if male_lines:
        test_lines.append(male_lines[0])

    # Третья строка - женский диалог
    female_lines = [l for l in ubf.lines if l.type == "dialogue" and l.speaker == "female"]
    if female_lines:
        test_lines.append(female_lines[0])

    print(f"Тестирую синтез на {len(test_lines)} строках:")
    for i, line in enumerate(test_lines, 1):
        seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
        print(f"  {i}. Line {line.idx}{seg_info} ({line.speaker}): {line.original[:70]}...")

    # Создаем синтезатор
    try:
        synthesizer = VoiceSynthesizer()

        successful_tests = 0
        for i, line in enumerate(test_lines, 1):
            print(f"\n📝 Тест {i}/{len(test_lines)}: Line {line.idx}")
            print(f"   Тип: {line.type}, Спикер: {line.speaker}")
            print(f"   Текст: {line.original}")

            try:
                # Генерируем имя файла
                if line.is_segment:
                    base_id = line.base_line_id if line.base_line_id is not None else line.idx
                    filename = f"DEBUG_{base_id:05d}_{line.speaker or 'narrator'}_seg{line.segment_index}.wav"
                else:
                    filename = f"DEBUG_{line.idx:05d}_{line.speaker or 'narrator'}.wav"

                debug_file = test_dir / filename

                # Если файл уже есть, удаляем
                if debug_file.exists():
                    debug_file.unlink()

                print(f"   Создаю файл: {filename}")
                start_time = time.time()

                # Пробуем синтезировать с дополнительной диагностикой
                result_path = synthesizer._synthesize_line(line, test_dir)

                elapsed = time.time() - start_time
                print(f"   ⏱️  Время синтеза: {elapsed:.2f} сек")

                if result_path and result_path.exists():
                    # Проверяем файл
                    import soundfile as sf
                    import numpy as np

                    try:
                        audio, sr = sf.read(result_path)
                        duration = len(audio) / sr
                        file_size = result_path.stat().st_size / 1024
                        max_amplitude = np.max(np.abs(audio))

                        print(f"   ✅ Файл создан успешно!")
                        print(f"      Размер: {file_size:.1f} KB")
                        print(f"      Длительность: {duration:.2f} сек")
                        print(f"      Частота: {sr} Гц")
                        print(f"      Макс амплитуда: {max_amplitude:.4f}")

                        if max_amplitude < 0.01:
                            print(f"   ⚠️  ВНИМАНИЕ: файл очень тихий!")
                        else:
                            print(f"   🔊 Звук есть в файле!")
                            successful_tests += 1

                        # Проверяем несколько сэмплов
                        if len(audio) > 10:
                            print(f"      Первые 5 сэмплов: {audio[:5]}")
                            print(f"      Среднее значение: {np.mean(np.abs(audio)):.6f}")

                    except Exception as e:
                        print(f"   ❌ Ошибка чтения файла: {e}")
                else:
                    print(f"   ❌ Файл не создан или не найден!")

            except Exception as e:
                print(f"   ❌ Ошибка синтеза: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n📊 ИТОГ тестирования: {successful_tests}/{len(test_lines)} успешно")

        if successful_tests > 0:
            print("✅ Stage 4 должен работать!")
            return True
        else:
            print("❌ Stage 4 не работает ни на одной строке")
            return False

    except Exception as e:
        print(f"❌ Ошибка инициализации синтезатора: {e}")
        import traceback
        traceback.print_exc()
        return False


def clean_directory(dir_path: Path):
    """Очищает директорию, сохраняя структуру"""
    if dir_path.exists():
        # Удаляем только файлы, сохраняем поддиректории
        for item in dir_path.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                # Очищаем поддиректории
                for sub_item in item.rglob("*"):
                    if sub_item.is_file():
                        sub_item.unlink()


def run_pipeline():
    """Основной пайплайн с детальной отладкой"""
    print("=" * 60)
    print("🚀 ОТЛАДОЧНЫЙ ПАЙПЛАЙН (С CUDA ПРОВЕРКОЙ)")
    print("=" * 60)

    # Сначала проверяем CUDA
    cuda_available = check_cuda_environment()

    if not cuda_available:
        print("\n⚠️  CUDA не доступна! Синтез будет медленным или может не работать.")
        proceed = input("Продолжить без CUDA? (y/n): ")
        if proceed.lower() != 'y':
            print("Выход...")
            return

    # Файл книги
    book = Path("storage/books/book.txt")
    if not book.exists():
        print(f"❌ Файл книги не найден: {book}")
        return

    print(f"\n📖 Книга: {book}")

    # Проверяем содержимое книги
    with open(book, 'r', encoding='utf-8') as f:
        content = f.read()
        lines_count = len(content.split('\n'))
        print(f"Строк в файле: {lines_count}")
        print(f"Символов: {len(content)}")

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

    # Примеры строк
    print("\n  Примеры строк (первые 5):")
    for i, line in enumerate(ubf.lines[:5]):
        seg_info = ""
        if line.is_segment:
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"
        text_preview = line.original[:80] + "..." if len(line.original) > 80 else line.original
        print(f"    {i + 1}. ID:{line.idx}{seg_info} ({line.type}/{line.speaker}): {text_preview}")

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

    # ========== STAGE 3 ==========
    print("\n" + "=" * 40)
    print("STAGE 3: ЭМОЦИИ")
    print("=" * 40)

    emotion_resolver = EmotionResolver()
    ubf = emotion_resolver.process(ubf)

    print("✅ Эмоции определены")

    # ========== ДЕТАЛЬНАЯ ОТЛАДКА STAGE 4 ==========
    print("\n" + "=" * 40)
    print("🔧 ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА STAGE 4")
    print("=" * 40)

    # Создаём директории
    audio_dir = Path("storage/audio")
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Очищаем старые файлы, но сохраняем директории
    clean_directory(audio_dir)

    # Запускаем детальную отладку Stage 4
    stage4_works = debug_stage_4_detailed(ubf, audio_dir)

    if not stage4_works:
        print("\n⚠️  Stage 4 не прошел предварительную проверку!")
        print("   Продолжаем с созданием тестовых файлов...")

    # ========== STAGE 4 (полный синтез) ==========
    print("\n" + "=" * 40)
    print("STAGE 4: ПОЛНЫЙ СИНТЕЗ РЕЧИ")
    print("=" * 40)

    synthesizer = VoiceSynthesizer()

    try:
        # Создаем поддиректорию для сырых файлов
        raw_dir = audio_dir / "raw"
        raw_dir.mkdir(exist_ok=True)

        print(f"Начинаю полный синтез {len(ubf.lines)} строк...")
        start_time = time.time()

        synthesizer.process(ubf, out_dir=raw_dir)

        elapsed = time.time() - start_time
        print(f"✅ Синтез завершён за {elapsed:.1f} секунд")

        # Проверяем созданные файлы
        wav_files = list(raw_dir.glob("*.wav"))
        print(f"  Создано файлов: {len(wav_files)}")

        if wav_files:
            print("  Примеры файлов:")
            for file in wav_files[:3]:
                file_size_kb = file.stat().st_size / 1024
                print(f"    {file.name} ({file_size_kb:.1f} KB)")

            # Проверяем что файлы не пустые
            print("  Проверка файлов на пустоту:")
            empty_files = 0
            for file in wav_files[:5]:  # Проверяем первые 5
                file_size = file.stat().st_size
                if file_size < 1024:  # Меньше 1KB
                    print(f"    ⚠️  {file.name}: пустой ({file_size} байт)")
                    empty_files += 1
                else:
                    print(f"    ✅ {file.name}: OK ({file_size} байт)")

            if empty_files > 0:
                print(f"  ⚠️  Найдено {empty_files} пустых файлов!")

        # Обновляем audio_path в строках для Stage 4.5 и 5
        files_found = 0
        for line in ubf.lines:
            if line.is_segment:
                base_id = line.base_line_id if line.base_line_id is not None else line.idx
                seg_idx = line.segment_index or 0
                expected_file = raw_dir / f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav"
            else:
                expected_file = raw_dir / f"{line.idx:05d}_{line.speaker or 'narrator'}.wav"

            if expected_file.exists():
                line.audio_path = str(expected_file)
                files_found += 1
            else:
                # Пробуем найти файл с другим именем
                pattern = f"*{line.idx:05d}*{line.speaker or 'narrator'}*.wav"
                matching_files = list(raw_dir.glob(pattern))
                if matching_files:
                    line.audio_path = str(matching_files[0])
                    files_found += 1
                    print(f"  🔍 Найден альтернативный файл для line {line.idx}: {matching_files[0].name}")

        print(f"  Найдено audio_path: {files_found}/{len(ubf.lines)}")

    except Exception as e:
        print(f"❌ Ошибка синтеза: {e}")
        import traceback
        traceback.print_exc()

        # Создаём тестовые файлы с тоном (не тишина)
        print("\n⚠️  Создаю тестовые файлы с тоном...")
        raw_dir = audio_dir / "raw"
        raw_dir.mkdir(exist_ok=True)

        import numpy as np
        import soundfile as sf

        created_files = 0
        for line in ubf.lines:
            if line.is_segment:
                base_id = line.base_line_id if line.base_line_id is not None else line.idx
                seg_idx = line.segment_index or 0
                filename = f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav"
            else:
                filename = f"{line.idx:05d}_{line.speaker or 'narrator'}.wav"

            test_file = raw_dir / filename

            # Создаем тестовый аудио файл с тоном (не тишина!)
            duration = 1.0  # секунда
            sr = 22050
            t = np.linspace(0, duration, int(sr * duration))
            # Синусоида 440 Гц (нота Ля) с затуханием
            audio = 0.5 * np.sin(2 * np.pi * 440 * t)
            audio *= np.exp(-2 * t)  # Экспоненциальное затухание

            sf.write(test_file, audio, sr)
            line.audio_path = str(test_file)
            created_files += 1

        print(f"Создано {created_files} тестовых файлов с тоном 440 Гц")

    # ========== STAGE 4.5 ==========
    print("\n" + "=" * 40)
    print("STAGE 4.5: УЛУЧШЕНИЕ АУДИО")
    print("=" * 40)

    try:
        enhancer = create_enhancer("simple")
        ubf = enhancer.process(ubf, audio_dir)

        # Проверяем enhanced файлы
        enhanced_dir = audio_dir / "enhanced"
        if enhanced_dir.exists():
            enhanced_files = list(enhanced_dir.glob("*.wav"))
            print(f"✅ Улучшение завершено")
            print(f"  Обработано файлов: {len(enhanced_files)}")
        else:
            print("⚠️  Директория enhanced не создана")

    except Exception as e:
        print(f"⚠️  Ошибка Stage 4.5: {e}")
        print("  Продолжаем без улучшения аудио")

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
        # Проверяем доступность файлов перед сборкой
        available_files = 0
        for line in ubf.lines:
            if line.audio_path and Path(line.audio_path).exists():
                available_files += 1
            elif line.audio_path:
                # Пробуем найти файл
                path = Path(line.audio_path)
                filename = path.name
                # Ищем в raw директории
                raw_path = audio_dir / "raw" / filename
                if raw_path.exists():
                    line.audio_path = str(raw_path)
                    available_files += 1

        print(f"  Доступно файлов для сборки: {available_files}/{len(ubf.lines)}")

        if available_files == 0:
            print("⚠️  Нет доступных аудио файлов! Создаю тестовые с тоном...")
            test_dir = audio_dir / "test_assembly"
            test_dir.mkdir(exist_ok=True)

            import numpy as np
            import soundfile as sf

            for line in ubf.lines:
                if line.is_segment:
                    base_id = line.base_line_id if line.base_line_id is not None else line.idx
                    seg_idx = line.segment_index or 0
                    filename = f"{base_id:05d}_{line.speaker or 'narrator'}_seg{seg_idx}.wav"
                else:
                    filename = f"{line.idx:05d}_{line.speaker or 'narrator'}.wav"

                test_file = test_dir / filename
                # Создаем тестовый аудио файл с разными тонами для разных спикеров
                duration = 1.0
                sr = 22050
                t = np.linspace(0, duration, int(sr * duration))

                if line.speaker == "male":
                    freq = 220  # Более низкий тон для мужского голоса
                elif line.speaker == "female":
                    freq = 660  # Более высокий тон для женского голоса
                else:
                    freq = 440  # Средний тон для повествования

                audio = 0.3 * np.sin(2 * np.pi * freq * t)
                audio *= np.exp(-2 * t)  # Затухание

                sf.write(test_file, audio, sr)
                line.audio_path = str(test_file)
            print(f"  Создано {len(ubf.lines)} тестовых файлов с разными тонами")

        print(f"  Начинаю сборку аудио...")
        assembler.process(ubf, final_path)

        if final_path.exists():
            # Получаем информацию о файле
            import soundfile as sf
            import numpy as np

            audio, sr = sf.read(final_path)
            duration = len(audio) / sr
            size_mb = final_path.stat().st_size / 1024 / 1024
            max_amplitude = np.max(np.abs(audio))
            mean_amplitude = np.mean(np.abs(audio))

            print(f"✅ Сборка завершена!")
            print(f"  Файл: {final_path}")
            print(f"  Длительность: {duration:.2f} секунд ({duration / 60:.2f} минут)")
            print(f"  Размер: {size_mb:.2f} MB")
            print(f"  Макс амплитуда: {max_amplitude:.4f}")
            print(f"  Средняя амплитуда: {mean_amplitude:.6f}")

            # Проверяем первые 5 секунд файла
            check_samples = min(5 * sr, len(audio))
            if check_samples > 0:
                segment = audio[:check_samples]
                segment_max = np.max(np.abs(segment))
                segment_mean = np.mean(np.abs(segment))
                print(f"  Первые 5 секунд: макс={segment_max:.4f}, среднее={segment_mean:.6f}")

                # Проверяем не тишина ли
                if max_amplitude < 0.001:
                    print("  ⚠️  ВНИМАНИЕ: финальный файл практически тишина!")
                elif max_amplitude < 0.01:
                    print("  ⚠️  Финальный файл очень тихий!")
                else:
                    print("  🔊 В финальном файле есть звук!")
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

    # Статистика по спикерам
    print("\nРаспределение спикеров:")
    speaker_stats = {}
    for line in ubf.lines:
        if line.speaker:
            speaker_stats[line.speaker] = speaker_stats.get(line.speaker, 0) + 1

    for speaker, count in speaker_stats.items():
        print(f"  {speaker}: {count} строк")

    if final_path.exists():
        print(f"\n✅ ПАЙПЛАЙН ЗАВЕРШЁН!")
        print(f"Аудиокнига: {final_path}")

        # Дополнительная проверка
        try:
            import soundfile as sf
            import numpy as np

            audio, sr = sf.read(final_path)
            print(f"Финальная проверка файла:")
            print(f"  Частота дискретизации: {sr} Гц")
            print(f"  Всего сэмплов: {len(audio):,}")

            # Проверяем есть ли хоть какой-то звук
            if np.max(np.abs(audio)) > 0.001:
                print(f"  ✅ Файл содержит звуковые данные")
            else:
                print(f"  ⚠️  Файл не содержит звуковых данных (тишина)")

        except Exception as e:
            print(f"  ⚠️  Не удалось проверить финальный файл: {e}")
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
        if line.remarks:
            print(f"    Ремарки: {[r.text for r in line.remarks]}")

    # Stage 2
    resolver = SpeakerResolver()
    ubf = resolver.process(ubf)

    print(f"\n✅ Stage 2: спикеры определены")
    for line in ubf.lines:
        seg_info = ""
        if line.is_segment:
            seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"
        print(f"  Line {line.idx}{seg_info}: {line.speaker}")

    # Stage 3
    emotion_resolver = EmotionResolver()
    ubf = emotion_resolver.process(ubf)

    print(f"\n✅ Stage 3: эмоции определены")
    for line in ubf.lines:
        if line.emotion:
            e = line.emotion
            print(f"  Line {line.idx}: энергия={e.energy:.2f}, темп={e.tempo:.2f}, пауза после={e.pause_after}ms")

    # Удаляем тестовый файл
    test_file.unlink()

    return ubf


def quick_test():
    """Быстрый тест всего пайплайна на минимальном тексте"""
    print("\n" + "=" * 60)
    print("⚡ БЫСТРЫЙ ТЕСТ ПАЙПЛАЙНА")
    print("=" * 60)

    test_content = """Это тестовое повествование. Оно должно быть разбито на сегменты, если достаточно длинное.
— Привет, — сказал он. — Как дела?
— Отлично! — ответила она с улыбкой. — А у тебя?
Длинное повествование, которое тоже должно быть разбито на части для лучшего синтеза через XTTS v2 модель.
— Я тоже в порядке, — сказал он задумчиво."""

    test_file = Path("storage/books/quick_test.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(test_content, encoding="utf-8")

    print(f"📝 Тестовый текст ({len(test_content)} символов):")
    print("-" * 40)
    print(test_content)
    print("-" * 40)

    # Только парсинг
    parser = StructuralParser(split_for_xtts=True)
    ubf = parser.parse_file(test_file)

    print(f"\n✅ Stage 1: {len(ubf.lines)} строк")
    for i, line in enumerate(ubf.lines):
        seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]" if line.is_segment else ""
        print(f"  {i + 1}. ID:{line.idx}{seg_info} ({line.type}): {line.original[:60]}...")

    test_file.unlink()


if __name__ == "__main__":
    try:
        print("Начинаю отладку пайплайна с проверкой CUDA...\n")

        # Быстрый тест (раскомментируйте для проверки)
        # quick_test()

        # Запускаем основной пайплайн
        ubf = run_pipeline()

        # Дополнительный тест конкретной строки
        # test_specific_line()

        print("\n" + "=" * 60)
        print("🎉 ОТЛАДКА ЗАВЕРШЕНА")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)