# core/pipeline/stage4_synthesizer.py
import tempfile
from pathlib import Path
import subprocess
import re
import time
import torch
from TTS.api import TTS

from core.models import UserBookFormat, Line


class VoiceSynthesizer:
    """
    Stage 4 — VoiceSynthesizer с принудительным использованием GPU
    """

    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    VOICE_MAP = {
        "narrator": "storage/voices/narrator.wav",
        "male": "storage/voices/male.wav",
        "female": "storage/voices/female.wav",
        None: "storage/voices/narrator.wav",
    }

    SAMPLE_RATE = 22050

    def __init__(self, device: str = "auto"):
        """
        :param device: "auto", "cuda", "cuda:0", "cpu"
        """
        self._setup_device(device)
        self._init_tts()

    def _setup_device(self, device: str):
        """Настраивает устройство для вычислений"""
        print("\n🔧 Настройка устройства для TTS:")

        # Проверяем доступность CUDA
        cuda_available = torch.cuda.is_available()
        print(f"  PyTorch CUDA доступна: {cuda_available}")

        if cuda_available:
            print(f"  CUDA устройств: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024 ** 3
                print(f"    GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")

        # Определяем устройство
        if device == "auto":
            if cuda_available:
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        # Проверяем что устройство доступно
        if self.device.startswith("cuda"):
            if not cuda_available:
                print(f"  ⚠️  Запрошено {self.device}, но CUDA недоступна!")
                self.device = "cpu"
            else:
                # Проверяем конкретный индекс GPU
                if ":" in self.device:
                    gpu_id = int(self.device.split(":")[1])
                    if gpu_id >= torch.cuda.device_count():
                        print(f"  ⚠️  GPU {gpu_id} не существует, использую GPU 0")
                        self.device = "cuda:0"

        print(f"  🎯 Используемое устройство: {self.device}")

        # Устанавливаем устройство по умолчанию для PyTorch
        if self.device.startswith("cuda"):
            torch.cuda.set_device(int(self.device.split(":")[1]) if ":" in self.device else 0)

    def _init_tts(self):
        """Инициализирует TTS модель"""
        print(f"\n🔊 Инициализация TTS модели: {self.MODEL_NAME}")

        try:
            # ВАЖНО: Сначала создаём TTS, потом перемещаем на устройство
            print(f"  Загрузка модели...")

            # Вариант 1: Прямая загрузка с указанием устройства
            use_gpu = self.device.startswith("cuda")

            self.tts = TTS(
                model_name=self.MODEL_NAME,
                progress_bar=False,  # Отключаем встроенный прогресс-бар
                gpu=use_gpu,
            )

            # 🔥 КРИТИЧЕСКИ ВАЖНО: Явно перемещаем модель на устройство
            if hasattr(self.tts, 'to'):
                print(f"  Перемещение модели на {self.device}...")
                self.tts = self.tts.to(self.device)
            else:
                print(f"  ⚠️  Модель не поддерживает .to() метод")

            print(f"  ✅ Модель загружена")

            # Тестируем что модель работает
            self._test_model()

        except Exception as e:
            print(f"  ❌ Ошибка загрузки TTS: {e}")

            # Fallback на CPU
            print("  🔄 Пробую загрузить на CPU...")
            self.device = "cpu"
            self.tts = TTS(
                model_name=self.MODEL_NAME,
                progress_bar=False,
                gpu=False,
            )
            print("  ✅ Модель загружена на CPU (fallback)")

    def _test_model(self):
        """Тестирует что модель работает"""
        print("  🧪 Тестирование модели...")

        try:
            # Создаём временный файл
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            # Тестовый синтез
            start_time = time.time()

            speaker_wav = self._get_test_speaker_wav()

            # 🔥 ТЕСТИРУЕМ ПРОБЛЕМУ С ОБРЕЗКОЙ
            test_text = "Лора - есть что то интересное"
            print(f"  Тестовый текст: '{test_text}'")

            cleaned_text = self._clean_text_for_tts(test_text)
            print(f"  После очистки: '{cleaned_text}'")

            self.tts.tts_to_file(
                text=cleaned_text,
                speaker_wav=speaker_wav,
                language="ru",
                file_path=str(tmp_path),
                split_sentences=False,
            )

            elapsed = time.time() - start_time

            if tmp_path.exists():
                file_size = tmp_path.stat().st_size
                print(f"  ✅ Тест пройден за {elapsed:.2f}с")
                print(f"     Размер файла: {file_size:,} байт")

                # Проверяем устройство модели
                self._check_model_device()

                tmp_path.unlink()
            else:
                print("  ⚠️  Тестовый файл не создан")

        except Exception as e:
            print(f"  ❌ Тест не пройден: {e}")
            import traceback
            traceback.print_exc()

    def _check_model_device(self):
        """Проверяет на каком устройстве находится модель"""
        try:
            # Пробуем определить устройство модели
            if hasattr(self.tts, 'model'):
                if hasattr(self.tts.model, 'device'):
                    print(f"  📍 Модель на устройстве: {self.tts.model.device}")
                elif hasattr(self.tts.model, 'parameters'):
                    # Проверяем первый параметр
                    first_param = next(self.tts.model.parameters(), None)
                    if first_param is not None:
                        print(f"  📍 Параметры модели на: {first_param.device}")
        except:
            pass

    def _get_test_speaker_wav(self) -> str:
        """Получает тестовый голосовой сэмпл"""
        # Создаём минимальный WAV файл если нет голосовых сэмплов
        test_wav = Path("storage/voices/test.wav")
        test_wav.parent.mkdir(parents=True, exist_ok=True)

        if not test_wav.exists():
            # Создаём минимальный WAV файл (0.1 секунда тишины)
            import wave
            import struct

            with wave.open(str(test_wav), 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.SAMPLE_RATE)

                # 0.1 секунда тишины
                frames = int(0.1 * self.SAMPLE_RATE)
                silent_data = struct.pack('<h', 0) * frames
                wav_file.writeframes(silent_data)

        return str(test_wav)

    def process(self, ubf: UserBookFormat, out_dir: Path) -> None:
        """Синтез аудио для всех строк"""
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n🔊 Stage 4: Синтез речи")
        print(f"  Устройство: {self.device}")
        print(f"  Строк для синтеза: {len(ubf.lines)}")
        print(f"  Выходная директория: {out_dir}")

        # Мониторинг GPU
        if self.device.startswith("cuda"):
            self._print_gpu_status("Перед началом синтеза")

        total_chars = 0
        processed = 0

        for i, line in enumerate(ubf.lines, 1):
            if not line.original or not line.original.strip():
                continue

            # Очищаем текст
            clean_text = self._clean_text_for_tts(line.original)
            total_chars += len(clean_text)

            # Пропускаем очень короткие строки
            if len(clean_text) < 3:
                continue

            # 🔥 ПРОВЕРКА: Сравниваем оригинал и очищенный текст
            if line.original != clean_text:
                print(f"  📝 Line {line.idx}:")
                print(f"    Оригинал: '{line.original}'")
                print(f"    Очищенный: '{clean_text}'")
                print(f"    Разница: {len(line.original)} → {len(clean_text)} симв.")

            # Логирование прогресса
            if i <= 5 or i % 10 == 0:
                seg_info = ""
                if line.is_segment:
                    seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"
                print(f"  [{i:3d}/{len(ubf.lines)}]{seg_info}: {clean_text[:50]}...")

            # Синтез
            try:
                wav_path = self._synthesize_line(line, out_dir, clean_text)
                line.audio_path = str(wav_path)
                processed += 1

                # Периодически показываем статус GPU
                if self.device.startswith("cuda") and i % 5 == 0:
                    self._print_gpu_status(f"После строки {i}")

            except Exception as e:
                print(f"  ⚠️  Ошибка синтеза строки {line.idx}: {e}")

        print(f"\n✅ Stage 4 завершён")
        print(f"  Обработано строк: {processed}/{len(ubf.lines)}")
        print(f"  Всего символов: {total_chars}")

        if self.device.startswith("cuda"):
            self._print_gpu_status("После синтеза")
            torch.cuda.empty_cache()  # Очищаем кэш CUDA

    def _print_gpu_status(self, context: str = ""):
        """Выводит статус GPU"""
        try:
            if torch.cuda.is_available():
                gpu_id = 0 if ":" not in self.device else int(self.device.split(":")[1])

                memory_allocated = torch.cuda.memory_allocated(gpu_id) / 1024 ** 3
                memory_reserved = torch.cuda.memory_reserved(gpu_id) / 1024 ** 3
                memory_total = torch.cuda.get_device_properties(gpu_id).total_memory / 1024 ** 3
                utilization = torch.cuda.utilization(gpu_id) if hasattr(torch.cuda, 'utilization') else 0

                print(f"  🎮 GPU {gpu_id} {context}:")
                print(f"    Память: {memory_allocated:.2f}/{memory_total:.2f} GB")
                print(f"    Зарезервировано: {memory_reserved:.2f} GB")
                if utilization > 0:
                    print(f"    Загрузка: {utilization}%")
        except:
            pass

    def _synthesize_line(self, line: Line, out_dir: Path, clean_text: str) -> Path:
        """Синтез одной строки"""
        # Определяем голос
        speaker_wav = self._resolve_voice(line.speaker)

        # Имя файла
        if line.is_segment:
            base_id = line.base_line_id if line.base_line_id is not None else line.idx
            filename = f"{base_id:05d}_{line.speaker or 'narrator'}_seg{line.segment_index}.wav"
        else:
            filename = f"{line.idx:05d}_{line.speaker or 'narrator'}.wav"

        final_path = out_dir / filename
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Если файл уже существует, пропускаем синтез
        if final_path.exists():
            print(f"    ⏭️  Файл уже существует: {filename}")
            return final_path

        # Временный файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        # Параметры синтеза
        speed = line.emotion.tempo if line.emotion else 1.0

        # Измеряем время синтеза
        start_time = time.time()

        try:
            # 🔥 СИНТЕЗ НА GPU
            self.tts.tts_to_file(
                text=clean_text,
                speaker_wav=speaker_wav,
                language="ru",
                speed=speed,
                split_sentences=False,  # Не разбиваем, уже сделано в Stage1
                file_path=str(tmp_path),
            )

            synthesis_time = time.time() - start_time

            # Логируем время для длинных строк
            if len(clean_text) > 80 or synthesis_time > 1.0:
                chars_per_sec = len(clean_text) / synthesis_time if synthesis_time > 0 else 0
                device_info = "GPU" if self.device.startswith("cuda") else "CPU"
                print(
                    f"    ⏱️  {device_info}: {len(clean_text)} симв. за {synthesis_time:.2f}с ({chars_per_sec:.0f} сим/с)")

            # Нормализация аудио
            normalized = self._normalize_audio(tmp_path)

            # Перемещаем файл
            import shutil
            shutil.move(str(normalized), str(final_path))

            return final_path

        except Exception as e:
            print(f"    ❌ Ошибка синтеза: {e}")
            raise
        finally:
            # Удаляем временный файл если он остался
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _clean_text_for_tts(self, text: str) -> str:
        """
        🔥 ИСПРАВЛЕННЫЙ МЕТОД ОЧИСТКИ ТЕКСТА
        Теперь НЕ удаляет буквы и важные символы
        """
        if not text:
            return ""

        # Сохраняем оригинал для отладки
        original_text = text

        # 1. Убираем только лишние пробелы (сохраняем одиночные пробелы)
        text = ' '.join(text.split())

        # 2. Обработка тире - разные типы тире заменяем на стандартное
        # НО НЕ УДАЛЯЕМ ТИРЕ!
        text = re.sub(r'[—–−]', '—', text)  # Заменяем все тире на стандартное

        # 3. Убираем пробелы после начального тире в диалогах
        # но оставляем пробел перед тире в середине предложения
        text = re.sub(r'^—\s+', '—', text)  # В начале строки

        # 4. Убираем только МНОЖЕСТВЕННЫЕ знаки препинания в конце
        # но оставляем одиночные
        text = re.sub(r'([.!?])\1+$', r'\1', text)  # !!! → !, ??? → ?

        # 5. Нормализуем многоточие
        text = re.sub(r'\.{3,}', '…', text)

        # 6. Убираем ТОЛЬКО ПУСТЫЕ кавычки (не трогаем кавычки с текстом)
        # Это было причиной проблемы! Старый код: text.replace('""', '')
        text = re.sub(r'""\s*""', '', text)  # Только если идут подряд
        text = re.sub(r"''\s*''", '', text)  # Только если идут подряд

        # 7. 🔥 ВАЖНО: НЕ УДАЛЯЕМ СКОБКИ, КАВЫЧКИ И ДРУГИЕ ВАЖНЫЕ СИМВОЛЫ
        # XTTS нормально работает с ними
        # Удаляем только реально проблемные символы:
        text = re.sub(r'[\*\#@%&_]', ' ', text)  # Заменяем на пробел, а не удаляем

        # 8. Убираем только лишние пробелы после очистки
        text = ' '.join(text.split())

        # 9. Если текст короткий и без пунктуации в конце - добавляем точку
        if len(text) > 0 and len(text) < 100:
            # Проверяем последний символ
            last_char = text[-1] if text else ''
            if last_char not in ['.', '!', '?', '…', '"', "'", '—', ')', ']', '}']:
                # Но не добавляем точку если это диалог с тире
                if not text.endswith('—'):
                    # И не добавляем точку к коротким словам (предлогам/союзам)
                    last_word = text.split()[-1].lower() if text.split() else ''
                    short_words = {'и', 'а', 'но', 'что', 'как', 'чтобы', 'если',
                                   'когда', 'где', 'куда', 'откуда', 'почему', 'зачем'}

                    if last_word not in short_words:
                        text = text + '.'

        # 10. Финальная очистка пробелов
        text = text.strip()

        # 11. Проверяем что текст не пустой
        if not text or text.isspace():
            text = "Текст отсутствует."

        # 12. 🔥 ОТЛАДКА: Сравниваем с оригиналом
        if original_text != text:
            print(f"    🔍 Очистка текста:")
            print(f"      Было: '{original_text}'")
            print(f"      Стало: '{text}'")

            # Проверяем не потерялись ли буквы
            if len(text) < len(original_text) * 0.8:  # Потеряно больше 20%
                print(f"      ⚠️  Возможно потеряны символы!")
                print(f"      Длина: {len(original_text)} → {len(text)} символов")

        return text

    def _resolve_voice(self, speaker: str | None) -> str:
        """Определяет путь к голосу"""
        path = Path(self.VOICE_MAP.get(speaker, self.VOICE_MAP[None]))

        # Создаём минимальный голосовой сэмпл если файла нет
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            self._create_minimal_wav(path)
            print(f"  ℹ️  Создан минимальный голосовой сэмпл: {path.name}")

        return str(path)

    def _create_minimal_wav(self, path: Path):
        """Создаёт минимальный WAV файл (тишина 0.2 секунды)"""
        import wave
        import struct

        with wave.open(str(path), 'w') as wav_file:
            wav_file.setnchannels(1)  # Моно
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.SAMPLE_RATE)

            # 0.2 секунды тишины
            frames = int(0.2 * self.SAMPLE_RATE)
            silent_data = struct.pack('<h', 0) * frames
            wav_file.writeframes(silent_data)

    def _normalize_audio(self, wav_path: Path) -> Path:
        """Нормализация аудио через ffmpeg"""
        normalized = wav_path.with_suffix(".norm.wav")

        subprocess.run(
            [
                "ffmpeg",
                "-i", str(wav_path),
                "-ac", "1",  # Моно
                "-ar", str(self.SAMPLE_RATE),
                "-acodec", "pcm_s16le",
                "-y",  # Перезаписать если существует
                str(normalized),
            ],
            check=True,
            capture_output=True,
            text=True
        )

        return normalized


# 🔥 ДОБАВЬТЕ ЭТУ ФУНКЦИЮ ДЛЯ ТЕСТИРОВАНИЯ
def test_text_cleaning():
    """Тестирует очистку текста"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ ОЧИСТКИ ТЕКСТА")
    print("=" * 60)

    test_cases = [
        # (оригинал, ожидаемый результат)
        ("Лора - есть что то интересное", "Лора — есть что то интересное."),
        ("«Привет» — сказал он.", "«Привет» — сказал он."),
        ("Что-то (в скобках) важно", "Что-то (в скобках) важно."),
        ("Она сказала: 'Иди сюда'", "Она сказала: 'Иди сюда'"),
        ("Много !!! знаков???", "Много ! знаков?"),
        ("Это... очень важно", "Это… очень важно."),
        ("Текст с *звездочками*", "Текст с звездочками."),
        ("Кавычки «» пустые", "Кавычки пустые."),
        ("— Здравствуйте, — сказала она.", "— Здравствуйте, — сказала она."),
        ("Название: 'Пираты Карибского моря'", "Название: 'Пираты Карибского моря'"),
    ]

    synthesizer = VoiceSynthesizer(device="cpu")

    print("Проверяю очистку текста:\n")

    all_passed = True
    for original, expected in test_cases:
        cleaned = synthesizer._clean_text_for_tts(original)

        # Для сравнения игнорируем возможную точку в конце
        cleaned_for_comparison = cleaned.rstrip('.')
        expected_for_comparison = expected.rstrip('.')

        passed = cleaned_for_comparison == expected_for_comparison

        print(f"Оригинал:    '{original}'")
        print(f"Очищенный:   '{cleaned}'")
        print(f"Ожидалось:   '{expected}'")
        print(f"Результат:   {'✅' if passed else '❌'}")
        print(f"Длина:       {len(original)} → {len(cleaned)} символов")
        print("-" * 40)

        if not passed:
            all_passed = False

    print(f"\nИтог: {'✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if all_passed else '❌ ЕСТЬ ПРОБЛЕМЫ'}")


class FastVoiceSynthesizer(VoiceSynthesizer):
    """Ускоренный синтезатор с кэшированием"""

    def __init__(self, device: str = "auto", cache_enabled: bool = True):
        super().__init__(device)
        self.cache_enabled = cache_enabled
        self.cache_dir = Path("storage/tts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if cache_enabled:
            print(f"  💾 Кэширование включено: {self.cache_dir}")

    def _synthesize_line(self, line: Line, out_dir: Path, clean_text: str) -> Path:
        """Синтез с кэшированием"""
        # Создаём ключ кэша
        import hashlib
        cache_key = f"{clean_text}_{line.speaker}_{line.emotion.tempo if line.emotion else 1.0}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_hash}.wav"

        # Имя выходного файла
        if line.is_segment:
            base_id = line.base_line_id if line.base_line_id is not None else line.idx
            filename = f"{base_id:05d}_{line.speaker or 'narrator'}_seg{line.segment_index}.wav"
        else:
            filename = f"{line.idx:05d}_{line.speaker or 'narrator'}.wav"

        final_path = out_dir / filename

        # Если файл уже существует в целевой директории
        if final_path.exists():
            return final_path

        # Если есть в кэше
        if self.cache_enabled and cache_file.exists():
            # Копируем из кэша
            import shutil
            shutil.copy2(cache_file, final_path)
            print(f"    💾 Из кэша: {len(clean_text)} симв.")
            return final_path

        # Иначе синтезируем
        result = super()._synthesize_line(line, out_dir, clean_text)

        # Сохраняем в кэш
        if self.cache_enabled and result.exists():
            import shutil
            shutil.copy2(result, cache_file)

        return result


# 🔥 ДОБАВЬТЕ ВЫЗОВ ТЕСТА В ОСНОВНОЙ СКРИПТ
if __name__ == "__main__":
    # Запуск теста очистки текста
    test_text_cleaning()