from __future__ import annotations

from pathlib import Path
from typing import Protocol

from llm.schemas import ProjectPlan


class PipelineObserver(Protocol):
    def status_changed(self, message: str) -> None: ...
    def progress_changed(self, percent: int) -> None: ...
    def plan_ready(self, plan: ProjectPlan) -> None: ...
    def scene_started(self, scene_id: int, total: int) -> None: ...
    def scene_completed(self, scene_id: int, total: int) -> None: ...
    def generation_completed(self, output: Path) -> None: ...


class NullObserver:
    def status_changed(self, message: str) -> None: pass
    def progress_changed(self, percent: int) -> None: pass
    def plan_ready(self, plan: ProjectPlan) -> None: pass
    def scene_started(self, scene_id: int, total: int) -> None: pass
    def scene_completed(self, scene_id: int, total: int) -> None: pass
    def generation_completed(self, output: Path) -> None: pass
