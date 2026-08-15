from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=8000)
    reference_image: Path | None = None
    duration_seconds: int = Field(default=30, ge=5, le=300)
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    style: str = Field(default="cinematic", min_length=1, max_length=100)
    voice_enabled: bool = True
    voice_language: Literal["bg", "en"] = "bg"
    voice_name: Literal["female", "male"] = "female"
    narration_mode: Literal["auto", "manual"] = "auto"
    narration_text: str | None = None
    seed: int = -1
    negative_prompt: str = ""
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)

    @model_validator(mode="after")
    def validate_manual_narration(self) -> "GenerationRequest":
        if self.narration_mode == "manual" and self.voice_enabled:
            if not self.narration_text or not self.narration_text.strip():
                raise ValueError("Manual narration text is required")
        if self.reference_image is not None and not self.reference_image.is_file():
            raise ValueError(f"Reference image does not exist: {self.reference_image}")
        return self

    @property
    def video_mode(self) -> Literal["text_to_video", "image_to_video"]:
        return "image_to_video" if self.reference_image else "text_to_video"
