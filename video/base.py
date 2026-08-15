from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class VideoGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    output_path: Path
    duration_seconds: float = Field(gt=0)
    width: int = Field(ge=64)
    height: int = Field(ge=64)
    fps: int = Field(ge=1)
    seed: int = -1
    steps: int = Field(default=20, ge=1)
    cfg: float = Field(default=6.0, ge=0)
    reference_image: Path | None = None
    camera_motion: str = ""
    preserve: list[str] = Field(default_factory=list)


class VideoGenerator(ABC):
    @abstractmethod
    def text_to_video(self, request: VideoGenerationRequest) -> Path:
        raise NotImplementedError

    @abstractmethod
    def image_to_video(self, request: VideoGenerationRequest) -> Path:
        raise NotImplementedError

    def cancel(self) -> None:
        """Request cancellation if supported."""

    def unload(self) -> None:
        """Release backend resources if supported."""
