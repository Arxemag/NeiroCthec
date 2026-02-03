import yaml
from pathlib import Path
from threading import Lock


class EmotionConfig:
    _lock = Lock()
    _data = None
    _path = Path("app/config/emotion_signals.yaml")

    @classmethod
    def load(cls):
        with cls._lock:
            with open(cls._path, "r", encoding="utf-8") as f:
                cls._data = yaml.safe_load(f)

    @classmethod
    def get(cls):
        if cls._data is None:
            cls.load()
        return cls._data

    @classmethod
    def reload(cls):
        cls.load()
