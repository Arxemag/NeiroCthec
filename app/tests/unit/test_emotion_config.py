from pathlib import Path

import pytest

from core.settings import EmotionConfig


def test_emotion_config_loads_yaml():
    """
    Базовая проверка: конфиг эмоций читается и возвращает словарь.
    """
    # Убедимся, что файл существует там, где его ожидает EmotionConfig
    config_path = Path("app/config/emotion_signals.yaml")
    assert config_path.exists(), f"Config file not found: {config_path}"

    data = EmotionConfig.get()

    assert isinstance(data, dict), "EmotionConfig.get() must return dict"
    assert data, "EmotionConfig.get() should not return empty config"

