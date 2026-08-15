from __future__ import annotations

import subprocess
from pathlib import Path

from core.config import TTSLanguageConfig
from tts.base import TTSEngine


class CommandTTSEngine(TTSEngine):
    """Adapter for a configurable local TTS executable; no text leaves the machine."""

    def __init__(self, config: TTSLanguageConfig, language: str) -> None:
        self.config = config
        self.language = language

    def synthesize(self, text: str, output_path: Path, voice: str, speed: float = 1.0) -> Path:
        if not self.config.command:
            raise RuntimeError(f"No command configured for {self.language} TTS")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        values = {
            "text": text, "output": str(output_path), "voice": voice, "speed": str(speed),
            "model_path": str(self.config.model_path), "language": self.language,
        }
        command = [part.format_map(values) for part in self.config.command]
        subprocess.run(command, check=True, capture_output=True, text=True)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"TTS command did not produce {output_path}")
        return output_path


class BulgarianTTSEngine(CommandTTSEngine):
    def __init__(self, config: TTSLanguageConfig) -> None:
        super().__init__(config, "bg")


class EnglishTTSEngine(CommandTTSEngine):
    def __init__(self, config: TTSLanguageConfig) -> None:
        super().__init__(config, "en")
