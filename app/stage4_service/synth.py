from pathlib import Path
import math
import numpy as np
import soundfile as sf

from stage4_service.schemas import TTSRequest


class MockSynthesizer:
    """MVP-синтезатор: генерирует простой сигнал и сохраняет WAV."""

    sample_rate = 22050

    def synthesize(self, request: TTSRequest, output_path: Path) -> int:
        text_len = max(len(request.text.strip()), 1)
        duration_sec = min(max(text_len * 0.06, 0.25), 8.0)
        samples = int(duration_sec * self.sample_rate)

        energy = max(0.1, min(request.emotion.energy, 2.0))
        pitch_factor = request.emotion.pitch
        speaker = request.speaker.lower()
        base_freq = 180 if speaker == "male" else 230 if speaker == "female" else 200
        freq = base_freq * (2 ** pitch_factor)

        t = np.linspace(0, duration_sec, samples, endpoint=False)
        waveform = 0.2 * energy * np.sin(2 * math.pi * freq * t)

        fade_len = max(1, int(0.01 * self.sample_rate))
        fade = np.linspace(0, 1, fade_len)
        waveform[:fade_len] *= fade
        waveform[-fade_len:] *= fade[::-1]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, waveform.astype(np.float32), self.sample_rate)
        return int(duration_sec * 1000)
