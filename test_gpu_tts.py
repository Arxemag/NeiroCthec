# test_gpu_tts.py
import torch
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))


def test_gpu():
    print("=" * 60)
    print("🎯 ТЕСТ GPU ДЛЯ TTS")
    print("=" * 60)

    # 1. Проверяем PyTorch
    print("\n1. Проверка PyTorch:")
    print(f"   Версия: {torch.__version__}")
    print(f"   CUDA доступна: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"   CUDA версия: {torch.version.cuda}")
        print(f"   GPU устройств: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            name = torch.cuda.get_device_name(i)
            memory = torch.cuda.get_device_properties(i).total_memory / 1024 ** 3
            print(f"   GPU {i}: {name} ({memory:.1f} GB)")

        # Тест скорости GPU
        print("\n2. Тест скорости GPU:")
        try:
            # Большая матрица для теста
            size = 10000
            a = torch.randn(size, size).cuda()
            b = torch.randn(size, size).cuda()

            torch.cuda.synchronize()
            import time
            start = time.time()
            c = torch.matmul(a, b)
            torch.cuda.synchronize()
            elapsed = time.time() - start

            print(f"   Матрица {size}x{size}: {elapsed:.2f} секунд")
            print(f"   Скорость: {(2 * size ** 3) / (elapsed * 1e9):.1f} GFLOPS")

            del a, b, c
            torch.cuda.empty_cache()
        except Exception as e:
            print(f"   ❌ Тест скорости не удался: {e}")

    # 2. Проверяем TTS
    print("\n3. Загрузка TTS...")
    try:
        from TTS.api import TTS

        # Пробуем загрузить с GPU
        use_gpu = torch.cuda.is_available()
        print(f"   Использовать GPU: {use_gpu}")

        tts = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=False,
            gpu=use_gpu,
        )

        print(f"   ✅ TTS загружен")

        # Проверяем устройство модели
        if hasattr(tts, 'model'):
            if hasattr(tts.model, 'device'):
                print(f"   Модель на: {tts.model.device}")
            elif hasattr(tts.model, 'parameters'):
                param = next(tts.model.parameters(), None)
                if param is not None:
                    print(f"   Параметры на: {param.device}")

        # Тестовый синтез
        print("\n4. Тестовый синтез...")
        import tempfile
        import time

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        start = time.time()

        # Нужен голосовой сэмпл
        test_wav = Path("storage/voices/test.wav")
        test_wav.parent.mkdir(parents=True, exist_ok=True)

        # Создаём минимальный WAV если нет
        if not test_wav.exists():
            import wave, struct
            with wave.open(str(test_wav), 'w') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(22050)
                frames = int(0.1 * 22050)
                f.writeframes(struct.pack('<h', 0) * frames)

        tts.tts_to_file(
            text="Тестирование синтеза речи на GPU.",
            speaker_wav=str(test_wav),
            language="ru",
            file_path=str(tmp_path),
            split_sentences=False,
        )

        elapsed = time.time() - start

        if tmp_path.exists():
            size = tmp_path.stat().st_size
            print(f"   ✅ Синтез за {elapsed:.2f} секунд")
            print(f"   Размер файла: {size:,} байт")
            tmp_path.unlink()
        else:
            print("   ❌ Файл не создан")

        test_wav.unlink(missing_ok=True)

    except Exception as e:
        print(f"   ❌ Ошибка TTS: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)

    # Рекомендация
    if torch.cuda.is_available():
        print("✅ GPU работает! TTS должен использовать CUDA.")
    else:
        print("❌ GPU не доступна. TTS будет работать на CPU (медленно).")


if __name__ == "__main__":
    test_gpu()