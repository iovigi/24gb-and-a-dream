from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from core.pipeline import GenerationPipeline, PipelineCancelled
from core.requests import GenerationRequest
from llm.schemas import ProjectPlan


class GenerationWorker(QObject):
    status = Signal(str)
    progress = Signal(int)
    plan = Signal(object)
    scene_started_signal = Signal(int, int)
    scene_completed_signal = Signal(int, int)
    completed = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, pipeline: GenerationPipeline, request: GenerationRequest) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.request = request
        pipeline.observer = self

    @Slot()
    def run(self) -> None:
        try:
            self.pipeline.run(self.request)
        except PipelineCancelled as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(_friendly_error(exc))
        finally:
            self.finished.emit()

    def cancel(self) -> None:
        self.pipeline.cancel()

    def status_changed(self, message: str) -> None:
        self.status.emit(message)

    def progress_changed(self, percent: int) -> None:
        self.progress.emit(percent)

    def plan_ready(self, plan: ProjectPlan) -> None:
        self.plan.emit(plan)

    def scene_started(self, scene_id: int, total: int) -> None:
        self.scene_started_signal.emit(scene_id, total)

    def scene_completed(self, scene_id: int, total: int) -> None:
        self.scene_completed_signal.emit(scene_id, total)

    def generation_completed(self, output: Path) -> None:
        self.completed.emit(str(output))


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "out of memory" in lowered or "cuda" in lowered and "memory" in lowered:
        return "CUDA ran out of memory. The 24 GB dream has temporarily ended."
    if "comfyui" in lowered:
        return text
    if "ffmpeg" in lowered:
        return text
    return f"Generation failed: {text}"
