# core/pipeline/stage4_synthesizer.py
import tempfile
from pathlib import Path
import subprocess
import re
import time
import torch
import yaml
from TTS.api import TTS

from core.models import UserBookFormat, Line


class VoiceSynthesizer:
    """
    Stage 4 — VoiceSynthesizer с чтением параметров из audio.yaml
    """

    def __init__(self, device: str = "auto", config_path: Path = None):
        """
        :param device: "auto", "cuda", "cuda:0", "cpu"
        :param config_path: путь к файлу конфигурации audio.yaml
        """
        # Загружаем конфигурацию
        if config_path is None:
            config_path = Path("app/audio.yaml")

        self.config = self._load_config(config_path)

        # Инициализируем параметры из конфига
        self._init_from_config()

        self._setup_device(device)
        self._init_tts()

    def _load_config(self, config_path: Path) -> dict:
        """Загружает конфигурацию из YAML файла"""
        print(f"\n📁 Загрузка конфигурации: {config_path}")

        if not config_path.exists():
            print(f"  ⚠️  Файл конфигурации не найден, используются значения по умолчанию")
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print("  ✅ Конфигурация загружена")
            return config or {}
        except Exception as e:
            print(f"  ❌ Ошибка загрузки конфигурации: {e}")
            return {}

    def _init_from_config(self):
        """Инициализирует параметры из конфигурации"""
        # Параметры движка
        engine_config = self.config.get('engine', {})
        self.MODEL_NAME = self._get_model_name(engine_config.get('type', 'xtts_v2'))
        self.LANGUAGE = engine_config.get('language', 'ru')
        self.DEVICE_CONFIG = engine_config.get('device', 'auto')

        # Голоса
        voices_config = self.config.get('voices', {})
        self.VOICE_MAP = {
            "narrator": voices_config.get('narrator', 'storage/voices/narrator.wav'),
            "male": voices_config.get('male', 'storage/voices/male.wav'),
            "female": voices_config.get('female', 'storage/voices/female.wav'),
            None: voices_config.get('narrator', 'storage/voices/narrator.wav'),
        }

        # XTTS параметры
        xtts_config = self.config.get('xtts', {})
        self.TEMPERATURE = xtts_config.get('temperature', 1.0)
        self.TOP_K = xtts_config.get('top_k', 50)
        self.TOP_P = xtts_config.get('top_p', 1.0)
        self.REPETITION_PENALTY = xtts_config.get('repetition_penalty', 2.8)
        self.SPEED_BASE = xtts_config.get('speed_base', 1.0)

        # Аудио параметры
        paths_config = self.config.get('paths', {})
        self.OUTPUT_DIR = Path(paths_config.get('output_dir', 'storage/audio'))
        self.SAMPLE_RATE = 22050  # Фиксировано для XTTS

        # Вывод загруженных параметров
        print("  📊 Параметры из конфига:")
        print(f"    Модель: {self.MODEL_NAME}")
        print(f"    Язык: {self.LANGUAGE}")
        print(f"    Скорость: {self.SPEED_BASE}")
        print(f"    Temperature: {self.TEMPERATURE}")
        print(f"    Top-K: {self.TOP_K}, Top-P: {self.TOP_P}")
        print(f"    Repetition penalty: {self.REPETITION_PENALTY}")

    def _get_model_name(self, engine_type: str) -> str:
        """Преобразует тип движка в имя модели TTS"""
        model_map = {
            'xtts_v2': 'tts_models/multilingual/multi-dataset/xtts_v2',
        }
        return model_map.get(engine_type, 'tts_models/multilingual/multi-dataset/xtts_v2')

    def _setup_device(self, device: str):
        """Настраивает устройство для вычислений"""
        print("\n🔧 Настройка устройства для TTS:")

        # Используем device из аргумента или из конфига
        if device == "auto":
            device = self.DEVICE_CONFIG

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
        """Инициализирует TTS модель с параметрами из конфига"""
        print(f"\n🔊 Инициализация TTS модели: {self.MODEL_NAME}")

        try:
            use_gpu = self.device.startswith("cuda")
            print(f"  Загрузка модели...")

            # Создаем TTS с параметрами из конфига
            self.tts = TTS(
                model_name=self.MODEL_NAME,
                progress_bar=False,
                gpu=use_gpu,
            )

            print(f"  ✅ Модель загружена")

            # Тестируем что модель работает
            self._test_model()

        except Exception as e:
            print(f"  ❌ Ошибка загрузки TTS: {e}")
            import traceback
            traceback.print_exc()
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
        """Тестирует что модель работает с параметрами из конфига"""
        print("  🧪 Тестирование модели...")

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            speaker_wav = self._get_test_speaker_wav()
            test_text = "Лора - есть что то интересное"
            cleaned_text = self._clean_text_for_tts(test_text)

            start_time = time.time()

            # Используем параметры из конфига
            self.tts.tts_to_file(
                text=cleaned_text,
                speaker_wav=speaker_wav,
                language=self.LANGUAGE,
                file_path=str(tmp_path),
                split_sentences=False,
            )

            elapsed = time.time() - start_time

            if tmp_path.exists():
                file_size = tmp_path.stat().st_size
                print(f"  ✅ Тест пройден за {elapsed:.2f}с")
                print(f"     Размер файла: {file_size:,} байт")
                tmp_path.unlink()
            else:
                print("  ⚠️  Тестовый файл не создан")

        except Exception as e:
            print(f"  ❌ Тест не пройден: {e}")
            import traceback
            traceback.print_exc()

    def _get_test_speaker_wav(self) -> str:
        """Получает тестовый голосовой сэмпл"""
        test_wav = Path("storage/voices/test.wav")
        test_wav.parent.mkdir(parents=True, exist_ok=True)

        if not test_wav.exists():
            import wave
            import struct

            with wave.open(str(test_wav), 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.SAMPLE_RATE)
                frames = int(0.1 * self.SAMPLE_RATE)
                silent_data = struct.pack('<h', 0) * frames
                wav_file.writeframes(silent_data)

        return str(test_wav)

    def process(self, ubf: UserBookFormat, out_dir: Path = None) -> None:
        """Синтез аудио для всех строк"""
        # Используем out_dir из аргумента или из конфига
        if out_dir is None:
            out_dir = self.OUTPUT_DIR / "raw"

        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n🔊 Stage 4: Синтез речи")
        print(f"  Устройство: {self.device}")
        print(f"  Язык: {self.LANGUAGE}")
        print(f"  Скорость: {self.SPEED_BASE}")
        print(f"  Строк для синтеза: {len(ubf.lines)}")
        print(f"  Выходная директория: {out_dir}")

        # Мониторинг GPU
        if self.device.startswith("cuda"):
            self._print_gpu_status("Перед началом синтеза")

        total_chars = 0
        processed = 0
        start_time = time.time()

        # 🔥 ИСПРАВЛЕНИЕ: Добавляем реальную обработку строк
        for i, line in enumerate(ubf.lines, 1):
            if not line.original or not line.original.strip():
                continue

            # Очищаем текст
            clean_text = self._clean_text_for_tts(line.original)
            total_chars += len(clean_text)

            # Пропускаем очень короткие строки
            if len(clean_text) < 3:
                continue

            # Показываем отладочную информацию для первых строк
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
                import traceback
                traceback.print_exc()

        total_time = time.time() - start_time

        print(f"\n✅ Stage 4 завершён")
        print(f"  Время синтеза: {total_time:.2f} секунд")
        print(f"  Обработано строк: {processed}/{len(ubf.lines)}")
        print(f"  Всего символов: {total_chars}")

        # Подсчитываем реально созданные файлы
        created_files = sum(1 for line in ubf.lines if line.audio_path and Path(line.audio_path).exists())
        print(f"  Создано файлов: {created_files}")
        print(f"  Найдено audio_path: {created_files}/{len(ubf.lines)}")

        if self.device.startswith("cuda"):
            self._print_gpu_status("После синтеза")
            torch.cuda.empty_cache()

    def _print_gpu_status(self, context: str = ""):
        """Выводит статус GPU"""
        try:
            if torch.cuda.is_available():
                gpu_id = 0 if ":" not in self.device else int(self.device.split(":")[1])

                memory_allocated = torch.cuda.memory_allocated(gpu_id) / 1024 ** 3
                memory_reserved = torch.cuda.memory_reserved(gpu_id) / 1024 ** 3
                memory_total = torch.cuda.get_device_properties(gpu_id).total_memory / 1024 ** 3

                print(f"  🎮 GPU {gpu_id} {context}:")
                print(f"    Память: {memory_allocated:.2f}/{memory_total:.2f} GB")
                print(f"    Зарезервировано: {memory_reserved:.2f} GB")
        except:
            pass

    def _synthesize_line(self, line: Line, out_dir: Path, clean_text: str) -> Path:
        """Синтез одной строки с параметрами из конфига"""
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

        # Используем базовую скорость из конфига и множитель из эмоции
        speed = self.SPEED_BASE * (line.emotion.tempo if line.emotion else 1.0)

        # Измеряем время синтеза
        start_time = time.time()

        try:
            # Синтез с параметрами из конфига
            self.tts.tts_to_file(
                text=clean_text,
                speaker_wav=speaker_wav,
                language=self.LANGUAGE,
                speed=speed,
                split_sentences=False,
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

            print(f"    ✅ Создан: {filename}")

            return final_path

        except Exception as e:
            print(f"    ❌ Ошибка синтеза: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # Удаляем временный файл если он остался
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _clean_text_for_tts(self, text: str) -> str:
        """Очистка текста для TTS"""
        if not text:
            return ""

        original_text = text

        # 1. Убираем только лишние пробелы
        text = ' '.join(text.split())

        # 2. Обработка тире
        text = re.sub(r'[—–−]', '—', text)
        text = re.sub(r'^—\s+', '—', text)

        # 3. Убираем множественные знаки препинания в конце
        text = re.sub(r'([.!?])\1+$', r'\1', text)

        # 4. Нормализуем многоточие
        text = re.sub(r'\.{3,}', '…', text)

        # 5. Убираем ТОЛЬКО ПУСТЫЕ кавычки
        text = re.sub(r'""\s*""', '', text)
        text = re.sub(r"''\s*''", '', text)

        # 6. Заменяем проблемные символы на пробел
        text = re.sub(r'[\*\#@%&_]', ' ', text)

        # 7. Убираем только лишние пробелы после очистки
        text = ' '.join(text.split())

        # 8. Если текст короткий и без пунктуации в конце - добавляем точку
        if len(text) > 0 and len(text) < 100:
            last_char = text[-1] if text else ''
            if last_char not in ['.', '!', '?', '…', '"', "'", '—', ')', ']', '}']:
                if not text.endswith('—'):
                    last_word = text.split()[-1].lower() if text.split() else ''
                    short_words = {'и', 'а', 'но', 'что', 'как', 'чтобы', 'если',
                                   'когда', 'где', 'куда', 'откуда', 'почему', 'зачем'}
                    if last_word not in short_words:
                        text = text + '.'

        # 9. Финальная очистка пробелов
        text = text.strip()

        # 10. Проверяем что текст не пустой
        if not text or text.isspace():
            text = "Текст отсутствует."

        # Отладочный вывод
        if original_text != text:
            print(f"    🔍 Очистка текста:")
            print(f"      Было: '{original_text}'")
            print(f"      Стало: '{text}'")

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
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.SAMPLE_RATE)
            frames = int(0.2 * self.SAMPLE_RATE)
            silent_data = struct.pack('<h', 0) * frames
            wav_file.writeframes(silent_data)

    def _normalize_audio(self, wav_path: Path) -> Path:
        """Нормализация аудио через ffmpeg"""
        normalized = wav_path.with_suffix(".norm.wav")

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-i", str(wav_path),
                    "-ac", "1",
                    "-ar", str(self.SAMPLE_RATE),
                    "-acodec", "pcm_s16le",
                    "-y",
                    str(normalized),
                ],
                check=True,
                capture_output=True,
                text=True
            )
            return normalized
        except subprocess.CalledProcessError as e:
            print(f"    ⚠️  Ошибка нормализации: {e}")
            # Возвращаем оригинальный файл если нормализация не удалась
            return wav_path


# Остальной код остается без изменений...

class FastVoiceSynthesizer(VoiceSynthesizer):
    """Ускоренный синтезатор с кэшированием"""

    def __init__(self, device: str = "auto", config_path: Path = None, cache_enabled: bool = True):
        super().__init__(device, config_path)
        self.cache_enabled = cache_enabled
        self.cache_dir = Path("storage/tts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if cache_enabled:
            print(f"  💾 Кэширование включено: {self.cache_dir}")

    def _synthesize_line(self, line: Line, out_dir: Path, clean_text: str) -> Path:
        """Синтез с кэшированием"""
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


def test_text_cleaning():
    """Тестирует очистку текста"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ ОЧИСТКИ ТЕКСТА")
    print("=" * 60)

    test_cases = [
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


if __name__ == "__main__":
    test_text_cleaning()
