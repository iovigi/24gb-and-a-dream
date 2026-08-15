from __future__ import annotations

import math

from core.requests import GenerationRequest
from llm.base import LLMEngine
from llm.schemas import (
    DirectorInstructions,
    NarratorInstructions,
    ProjectPlan,
    ProjectSettings,
    Scene,
    VoiceOverSettings,
)


class MockLLMEngine(LLMEngine):
    def create_director_plan(self, request: GenerationRequest) -> ProjectPlan:
        scene_count = max(1, math.ceil(request.duration_seconds / 10))
        base = request.duration_seconds / scene_count
        scenes: list[Scene] = []
        for index in range(scene_count):
            narration = ""
            if request.voice_enabled:
                if request.narration_mode == "manual":
                    narration = request.narration_text if index == 0 and request.narration_text else ""
                elif request.voice_language == "bg":
                    narration = f"Сцена {index + 1} разгръща историята с кинематографичен ритъм."
                else:
                    narration = f"Scene {index + 1} unfolds the story with cinematic rhythm."
            preserve = ["reference subject identity", "major composition", "important colors"] if request.reference_image else []
            scenes.append(Scene(
                id=index + 1,
                duration_seconds=base,
                director=DirectorInstructions(
                    visual_prompt=f"{request.style} scene inspired by: {request.prompt}",
                    negative_prompt=request.negative_prompt,
                    camera_motion="slow cinematic push-in",
                    motion=["natural environmental motion", "subtle subject movement"],
                    preserve=preserve,
                ),
                narrator=NarratorInstructions(text=narration, emotion="dramatic", pace="medium"),
            ))
        return ProjectPlan(
            project=ProjectSettings(
                title=request.prompt[:80].strip(), duration_seconds=request.duration_seconds,
                aspect_ratio=request.aspect_ratio, style=request.style, language=request.voice_language,
            ),
            voice_over=VoiceOverSettings(
                enabled=request.voice_enabled, language=request.voice_language,
                voice=request.voice_name, narration_mode=request.narration_mode,
            ),
            scenes=scenes,
        )
