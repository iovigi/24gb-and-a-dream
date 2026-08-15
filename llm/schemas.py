from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectSettings(ContractModel):
    title: str = Field(min_length=1, max_length=160)
    duration_seconds: float = Field(gt=0, le=3600)
    aspect_ratio: Literal["16:9", "9:16", "1:1"]
    style: str = Field(min_length=1, max_length=100)
    language: Literal["bg", "en"]


class VoiceOverSettings(ContractModel):
    enabled: bool
    language: Literal["bg", "en"]
    voice: Literal["female", "male"]
    narration_mode: Literal["auto", "manual"]


class DirectorInstructions(ContractModel):
    visual_prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str = Field(default="", max_length=2000)
    camera_motion: str = Field(default="static", max_length=300)
    motion: list[str] = Field(default_factory=list, max_length=20)
    preserve: list[str] = Field(default_factory=list, max_length=20)


class NarratorInstructions(ContractModel):
    text: str = Field(default="", max_length=8000)
    emotion: str = Field(default="neutral", max_length=100)
    pace: Literal["slow", "medium", "fast"] = "medium"


class Scene(ContractModel):
    id: int = Field(ge=1)
    duration_seconds: float = Field(gt=0, le=60)
    director: DirectorInstructions
    narrator: NarratorInstructions


class ProjectPlan(ContractModel):
    project: ProjectSettings
    voice_over: VoiceOverSettings
    scenes: list[Scene] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_contract(self) -> "ProjectPlan":
        ids = [scene.id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("Scene IDs must be unique")
        if self.project.language != self.voice_over.language:
            raise ValueError("Project and voice-over languages must match")
        scene_duration = sum(scene.duration_seconds for scene in self.scenes)
        if abs(scene_duration - self.project.duration_seconds) > 1.0:
            raise ValueError("Scene durations must match project duration within one second")
        if not self.voice_over.enabled and any(s.narrator.text for s in self.scenes):
            raise ValueError("Disabled voice-over must not contain narration")
        return self
