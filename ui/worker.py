from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from core.pipeline import GenerationPipeline, PipelineCancelled
from core.requests import GenerationRequest
from llm.schemas import ProjectPlan
from utils.crash import log_exception, note_activity

_logger = logging.getLogger("dream24gb.worker")


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
        # Nothing may escape this method: an exception crossing back into Qt's
        # C++ layer terminates the whole process without a message.
        try:
            note_activity("pipeline running")
            self.pipeline.run(self.request)
        except PipelineCancelled as exc:
            _logger.info("Pipeline cancelled: %s", exc)
            self.failed.emit(str(exc))
        except BaseException as exc:  # noqa: BLE001 - deliberate catch-all
            log_exception(exc, "Pipeline raised an unhandled exception")
            self.failed.emit(_friendly_error(exc))
        finally:
            try:
                self.finished.emit()
            except BaseException as exc:  # noqa: BLE001
                log_exception(exc, "Failed to emit worker finished signal")

    def cancel(self) -> None:
        _logger.info("Cancellation requested")
        note_activity("cancellation requested")
        self.pipeline.cancel()

    def status_changed(self, message: str) -> None:
        _logger.info("Status: %s", message)
        note_activity(message)
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
