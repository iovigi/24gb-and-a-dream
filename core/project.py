from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.requests import GenerationRequest
from llm.schemas import ProjectPlan

SceneStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ProjectStatus = Literal["created", "planning", "generating", "rendering", "completed", "failed", "cancelled"]


class VideoProject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    prompt: str
    reference_image: Path | None = None
    requested_duration: float
    aspect_ratio: str
    style: str
    voice_enabled: bool
    voice_language: str
    voice_name: str
    narration_mode: str
    narration_text: str | None = None
    director_plan: ProjectPlan | None = None
    project_directory: Path
    status: ProjectStatus = "created"
    scene_states: dict[str, SceneStatus] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def create(cls, request: GenerationRequest, projects_dir: Path) -> "VideoProject":
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        slug = _slugify(request.prompt)[:48] or "untitled"
        project_dir = projects_dir / f"{stamp}_{slug}"
        counter = 2
        while project_dir.exists():
            project_dir = projects_dir / f"{stamp}_{slug}_{counter}"
            counter += 1
        for child in ("input", "audio", "scenes", "subtitles", "output", "logs"):
            (project_dir / child).mkdir(parents=True, exist_ok=True)
        reference: Path | None = None
        if request.reference_image:
            reference = project_dir / "input" / f"reference{request.reference_image.suffix.lower()}"
            shutil.copy2(request.reference_image, reference)
        project = cls(
            id=str(uuid.uuid4()), prompt=request.prompt, reference_image=reference,
            requested_duration=request.duration_seconds, aspect_ratio=request.aspect_ratio,
            style=request.style, voice_enabled=request.voice_enabled,
            voice_language=request.voice_language, voice_name=request.voice_name,
            narration_mode=request.narration_mode, narration_text=request.narration_text,
            project_directory=project_dir,
        )
        project.save()
        return project

    @classmethod
    def load(cls, project_directory: str | Path) -> "VideoProject":
        path = Path(project_directory) / "project.json"
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.updated_at = datetime.now()
        _atomic_write(self.project_directory / "project.json", self.model_dump_json(indent=2))
        if self.director_plan is not None:
            _atomic_write(self.project_directory / "director_plan.json", self.director_plan.model_dump_json(indent=2))

    def initialize_scenes(self) -> None:
        if self.director_plan:
            for scene in self.director_plan.scenes:
                self.scene_states.setdefault(f"scene_{scene.id:03d}", "pending")
            self.save()

    def set_scene_status(self, scene_id: int, status: SceneStatus) -> None:
        self.scene_states[f"scene_{scene_id:03d}"] = status
        self.save()

    def scene_output(self, scene_id: int) -> Path:
        return self.project_directory / "scenes" / f"scene_{scene_id:03d}.mp4"

    def has_valid_scene_output(self, scene_id: int) -> bool:
        path = self.scene_output(scene_id)
        return self.scene_states.get(f"scene_{scene_id:03d}") == "completed" and path.is_file() and path.stat().st_size > 0


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9а-я]+", "_", value.lower().strip(), flags=re.IGNORECASE)
    return value.strip("_")


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
