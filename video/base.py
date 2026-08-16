from __future__ import annotations

import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

# ComfyUI's KSampler accepts 0 .. 2**64-1; keep well inside that.
MAX_SEED = 2**31 - 1


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

    def resolved_seed(self) -> int:
        """A concrete seed for the backend.

        The UI uses -1 for "surprise me", but ComfyUI's KSampler rejects any
        negative seed ("Value -1 smaller than min of 0"), so the convention has
        to be turned into a real number before the workflow is submitted. Each
        call returns a fresh value, so chunks generated from one request are not
        identical.
        """
        if self.seed >= 0:
            return self.seed
        return secrets.randbelow(MAX_SEED + 1)


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
