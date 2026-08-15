from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, output_path: Path, voice: str, speed: float = 1.0) -> Path:
        raise NotImplementedError

    def unload(self) -> None:
        """Release model resources. Implementations may override."""
