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

    # 2. TTS — только Qwen3 (Coqui удалён)
    print("\n3. TTS...")
    print("   Coqui TTS удалён. Озвучка только через Qwen3 (tts_engine_service).")
    print("   Модель: divyajot5005/Qwen3-TTS-12Hz-1.7B-Base-BNB-4bit")
    print("   Для проверки синтеза запустите: python -m tts_engine_service.app (в папке app) и запрос на :8020.")

    print("\n" + "=" * 60)

    if torch.cuda.is_available():
        print("✅ GPU работает! Qwen3-TTS в tts_engine_service может использовать CUDA/ROCm.")
    else:
        print("❌ GPU не доступна. TTS будет работать на CPU (медленно).")


if __name__ == "__main__":
    test_gpu()