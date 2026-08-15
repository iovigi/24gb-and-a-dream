from __future__ import annotations

import math
import wave
from pathlib import Path

from pydantic import BaseModel, Field

from llm.schemas import ProjectPlan


class SceneTiming(BaseModel):
    scene_id: int
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    clip_count: int = Field(ge=1)
    narration_text: str = ""


def audio_duration(path: Path) -> float:
    if path.suffix.lower() != ".wav":
        raise ValueError("Built-in duration reader supports WAV files only")
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / float(audio.getframerate())


def build_timeline(
    plan: ProjectPlan,
    audio_durations: dict[int, float] | None = None,
    clip_seconds: float = 5.0,
) -> list[SceneTiming]:
    if clip_seconds <= 0:
        raise ValueError("clip_seconds must be positive")
    cursor = 0.0
    result: list[SceneTiming] = []
    for scene in plan.scenes:
        measured = (audio_durations or {}).get(scene.id)
        duration = max(scene.duration_seconds, measured or 0.0)
        result.append(SceneTiming(
            scene_id=scene.id,
            start_seconds=cursor,
            end_seconds=cursor + duration,
            duration_seconds=duration,
            clip_count=max(1, math.ceil(duration / clip_seconds)),
            narration_text=scene.narrator.text,
        ))
        cursor += duration
    return result
