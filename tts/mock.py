from __future__ import annotations

import wave
from pathlib import Path

from tts.base import TTSEngine


class MockTTSEngine(TTSEngine):
    sample_rate = 16_000

    def synthesize(self, text: str, output_path: Path, voice: str, speed: float = 1.0) -> Path:
        del voice
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.25, len(text.split()) / (2.5 * speed)) if text.strip() else 0.25
        frame_count = int(duration * self.sample_rate)
        with wave.open(str(output_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(self.sample_rate)
            audio.writeframes(b"\0\0" * frame_count)
        return output_path
