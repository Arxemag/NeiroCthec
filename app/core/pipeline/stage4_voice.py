# core/pipeline/stage4_synthesizer.py
import tempfile
from pathlib import Path
import subprocess
import re

import torch
from TTS.api import TTS

from core.models import UserBookFormat, Line


class VoiceSynthesizer:
    """
    Stage 4 — VoiceSynthesizer
    🔥 ИСПРАВЛЕН: Корректная очистка текста, работа с сегментами
    """

    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    VOICE_MAP = {
        "narrator": "storage/voices/narrator.wav",
        "male": "storage/voices/male.wav",
        "female": "storage/voices/female.wav",
        None: "storage/voices/narrator.wav",
    }

    SAMPLE_RATE = 22050

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.tts = TTS(
            model_name=self.MODEL_NAME,
            progress_bar=True,
            gpu=self.device == "cuda",
        ).to(self.device)

        print(f"🔊 Stage 4: VoiceSynthesizer на {self.device}")

    def process(self, ubf: UserBookFormat, out_dir: Path) -> None:
        """Синтез аудио для всех строк"""
        out_dir.mkdir(parents=True, exist_ok=True)

        # Создаём поддиректорию для сырых файлов
        raw_dir = out_dir / "raw"
        raw_dir.mkdir(exist_ok=True)

        print(f"  Синтез {len(ubf.lines)} строк в {raw_dir}")

        for i, line in enumerate(ubf.lines, 1):
            if not line.original.strip():
                continue

            # Логирование
            seg_info = ""
            if line.is_segment:
                seg_info = f" [сегмент {line.segment_index + 1}/{line.segment_total}]"

            clean_text = self._clean_text_for_tts(line.original)
            print(f"  [{i}/{len(ubf.lines)}]{seg_info}: {clean_text[:60]}...")

            wav_path = self._synthesize_line(line, raw_dir)
            line.audio_path = str(wav_path)

        print(f"✅ Stage 4: Синтез завершён")

    def _synthesize_line(self, line: Line, out_dir: Path) -> Path:
        """Синтез одной строки"""
        # 🔥 ОЧИЩАЕМ текст перед синтезом
        clean_text = self._clean_text_for_tts(line.original)

        # Определяем голос
        speaker_wav = self._resolve_voice(line.speaker)

        # Временный файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        # Параметры синтеза
        speed = line.emotion.tempo if line.emotion else 1.0

        # 🔥 ИСПРАВЛЕНИЕ: Используем очищенный текст
        self.tts.tts_to_file(
            text=clean_text,  # ← ОЧИЩЕННЫЙ текст
            speaker_wav=speaker_wav,
            language="ru",
            speed=speed,
            split_sentences=False,  # Не разбиваем - уже сделано в Stage1
            file_path=str(tmp_path),
        )

        # Нормализация
        normalized = self._normalize_audio(tmp_path)

        # Имя файла
        if line.is_segment:
            base_id = line.base_line_id if line.base_line_id is not None else line.idx
            filename = f"{base_id:05d}_{line.speaker or 'narrator'}_seg{line.segment_index}.wav"
        else:
            filename = f"{line.idx:05d}_{line.speaker or 'narrator'}.wav"

        final_path = out_dir / filename
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Переносим файл
        import shutil
        shutil.move(str(normalized), str(final_path))

        return final_path

    def _clean_text_for_tts(self, text: str) -> str:
        """
        🔥 ИСПРАВЛЕННАЯ ОЧИСТКА ТЕКСТА ДЛЯ XTTS
        Убирает артефакты, которые вызывают "додумывание" окончаний
        """
        if not text:
            return ""

        # 1. Убираем лишние пробелы
        text = ' '.join(text.split())

        # 2. Заменяем несколько тире подряд на один
        text = re.sub(r'[—–−]{2,}', '—', text)

        # 3. Убираем пробелы вокруг тире (но оставляем после тире в начале диалога)
        if text.startswith('—'):
            text = '—' + text[1:].strip()

        # 4. Убираем лишние знаки препинания в конце
        # Но оставляем ! ? … (многоточие)
        text = re.sub(r'[.!?]+$', lambda m: m.group()[-1] if m.group() else '', text)

        # 5. Заменяем несколько точек на многоточие
        text = re.sub(r'\.{3,}', '…', text)

        # 6. Убираем пустые кавычки
        text = text.replace('«»', '').replace('""', '').replace("''", '')

        # 7. 🔥 ВАЖНО: Убираем "висячие" союзы и предлоги в конце
        # XTTS может добавить "понти", если текст заканчивается на предлог
        ending_words_to_check = ['и', 'а', 'но', 'что', 'как', 'чтобы', 'если', 'когда']
        words = text.split()
        if words and words[-1].lower() in ending_words_to_check:
            # Добавляем точку или обрезаем
            text = text.rstrip() + '.'

        # 8. Если текст короткий, добавляем точку если её нет
        if len(text) < 50 and not text.endswith(('.', '!', '?', '…')):
            text = text + '.'

        # 9. Убираем лишние запятые в конце
        text = text.rstrip(',;:')

        return text.strip()

    def _resolve_voice(self, speaker: str | None) -> Path:
        """Определяет путь к голосу"""
        path = Path(self.VOICE_MAP.get(speaker, self.VOICE_MAP[None]))
        if not path.exists():
            raise FileNotFoundError(f"Голос не найден: {path}")
        return path

    def _normalize_audio(self, wav_path: Path) -> Path:
        """Нормализация аудио"""
        normalized = wav_path.with_suffix(".norm.wav")

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

        wav_path.unlink(missing_ok=True)
        return normalized