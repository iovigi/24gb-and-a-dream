from __future__ import annotations

import logging
import threading
from pathlib import Path

from core.config import Settings
from core.events import NullObserver, PipelineObserver
from core.project import VideoProject
from core.requests import GenerationRequest
from llm.factory import LLMFactory
from render.factory import VideoRendererFactory
from render.subtitles import write_srt
from render.timeline import audio_duration, build_timeline
from tts.factory import TTSEngineFactory
from utils.gpu import release_gpu_memory
from utils.logging import configure_logging
from utils.paths import ensure_free_disk_space, resolution_for_aspect_ratio
from video.base import VideoGenerationRequest
from video.factory import VideoGeneratorFactory


class PipelineCancelled(InterruptedError):
    pass


class GenerationPipeline:
    def __init__(self, settings: Settings, observer: PipelineObserver | None = None) -> None:
        self.settings = settings
        self.observer = observer or NullObserver()
        self.cancel_event = threading.Event()
        self._video = None
        self._renderer = None
        self.logger = logging.getLogger("dream24gb")

    def cancel(self) -> None:
        self.cancel_event.set()
        if self._video:
            self._video.cancel()
        if self._renderer:
            self._renderer.cancel()

    def run(self, request: GenerationRequest, project: VideoProject | None = None) -> Path:
        self.cancel_event.clear()
        ensure_free_disk_space(self.settings.app.projects_dir, self.settings.app.min_free_disk_gb)
        project = project or VideoProject.create(request, self.settings.app.projects_dir)
        self.logger = configure_logging(project.project_directory)
        self.logger.info("Generation started project=%s mode=%s", project.id, request.video_mode)
        try:
            if project.director_plan is None:
                self._plan(project, request)
            else:
                self.observer.plan_ready(project.director_plan)
            self._check_cancelled()
            audio_paths, durations = self._synthesize(project, request)
            self._check_cancelled()
            timings = build_timeline(project.director_plan, durations, self.settings.video.clip_seconds)
            write_srt(timings, project.project_directory / "subtitles" / "subtitles.srt")
            scene_paths = self._generate_scenes(project, request, timings)
            self._check_cancelled()
            output = self._render(project, scene_paths, audio_paths)
            project.status = "completed"
            project.error = None
            project.save()
            self.observer.progress_changed(100)
            self.observer.status_changed("Video complete. The GPU may now reflect on its choices.")
            self.observer.generation_completed(output)
            self.logger.info("Generation completed output=%s", output)
            return output
        except (PipelineCancelled, InterruptedError) as exc:
            project.status = "cancelled"
            project.error = str(exc)
            for key, state in list(project.scene_states.items()):
                if state == "running":
                    project.scene_states[key] = "cancelled"
            project.save()
            self.logger.info("Generation cancelled")
            raise PipelineCancelled("Generation cancelled; completed assets were preserved") from exc
        except Exception as exc:
            project.status = "failed"
            project.error = str(exc)
            project.save()
            self.logger.exception("Generation failed")
            raise
        finally:
            self._video = None
            self._renderer = None
            release_gpu_memory()

    def _plan(self, project: VideoProject, request: GenerationRequest) -> None:
        project.status = "planning"
        project.save()
        self.observer.status_changed("Analyzing prompt...")
        self.observer.progress_changed(5)
        engine = LLMFactory.create(self.settings.llm)
        try:
            plan = engine.create_director_plan(request)
            if request.narration_mode == "manual" and request.voice_enabled:
                actual = "".join(scene.narrator.text for scene in plan.scenes)
                if actual != request.narration_text:
                    raise ValueError("The director changed manual narration text")
            project.director_plan = plan
            project.initialize_scenes()
            self.observer.plan_ready(plan)
            self.observer.progress_changed(15)
            self.logger.info("Director plan created scenes=%d", len(plan.scenes))
        finally:
            engine.unload()
            release_gpu_memory(engine)

    def _synthesize(self, project: VideoProject, request: GenerationRequest) -> tuple[list[Path], dict[int, float]]:
        if not request.voice_enabled:
            return [], {}
        self.observer.status_changed("Generating local narration...")
        engine = TTSEngineFactory.create(self.settings.tts, request.voice_language)
        paths: list[Path] = []
        durations: dict[int, float] = {}
        try:
            for scene in project.director_plan.scenes:
                self._check_cancelled()
                if not scene.narrator.text:
                    continue
                path = project.project_directory / "audio" / f"scene_{scene.id:03d}.wav"
                if not path.is_file() or path.stat().st_size == 0:
                    engine.synthesize(scene.narrator.text, path, request.voice_name, request.tts_speed)
                paths.append(path)
                durations[scene.id] = audio_duration(path)
            self.observer.progress_changed(30)
            self.logger.info("Narration generated language=%s files=%d", request.voice_language, len(paths))
            return paths, durations
        finally:
            engine.unload()
            release_gpu_memory(engine)

    def _generate_scenes(self, project: VideoProject, request: GenerationRequest, timings) -> list[Path]:
        project.status = "generating"
        project.save()
        self._video = VideoGeneratorFactory.create(self.settings)
        width, height = resolution_for_aspect_ratio(
            request.aspect_ratio, self.settings.video.default_width, self.settings.video.default_height,
        )
        total = len(project.director_plan.scenes)
        outputs: list[Path] = []
        timing_by_id = {timing.scene_id: timing for timing in timings}
        try:
            for index, scene in enumerate(project.director_plan.scenes, start=1):
                self._check_cancelled()
                timing = timing_by_id[scene.id]
                chunk_paths = _scene_chunk_paths(project, scene.id, timing.clip_count)
                if project.scene_states.get(f"scene_{scene.id:03d}") == "completed" and all(
                    path.is_file() and path.stat().st_size > 0 for path in chunk_paths
                ):
                    self.logger.info("Skipping completed scene=%d", scene.id)
                    outputs.extend(chunk_paths)
                    continue
                project.set_scene_status(scene.id, "running")
                self.observer.scene_started(scene.id, total)
                self.observer.status_changed(f"Scene {index} / {total} — GPU still alive")
                remaining = timing.duration_seconds
                for chunk_index, output in enumerate(chunk_paths, start=1):
                    self._check_cancelled()
                    chunk_duration = min(self.settings.video.clip_seconds, remaining)
                    remaining -= chunk_duration
                    video_request = VideoGenerationRequest(
                        prompt=_scene_prompt(scene), negative_prompt=scene.director.negative_prompt,
                        output_path=output, duration_seconds=chunk_duration,
                        width=width, height=height, fps=self.settings.video.default_fps,
                        seed=request.seed, steps=self.settings.video.default_steps,
                        cfg=self.settings.video.default_cfg, reference_image=project.reference_image,
                        camera_motion=scene.director.camera_motion, preserve=scene.director.preserve,
                    )
                    for attempt in range(self.settings.app.max_scene_retries + 1):
                        try:
                            if project.reference_image:
                                self._video.image_to_video(video_request)
                            else:
                                self._video.text_to_video(video_request)
                            break
                        except Exception:
                            if attempt >= self.settings.app.max_scene_retries:
                                project.set_scene_status(scene.id, "failed")
                                raise
                            self.logger.warning(
                                "Scene chunk retry scene=%d chunk=%d attempt=%d",
                                scene.id, chunk_index, attempt + 1, exc_info=True,
                            )
                project.set_scene_status(scene.id, "completed")
                outputs.extend(chunk_paths)
                self.observer.scene_completed(scene.id, total)
                self.observer.progress_changed(30 + round(index / total * 55))
            return outputs
        finally:
            if self._video:
                self._video.unload()
            release_gpu_memory(self._video)

    def _render(self, project: VideoProject, scene_paths: list[Path], audio_paths: list[Path]) -> Path:
        project.status = "rendering"
        project.save()
        self.observer.status_changed("Rendering final video...")
        self.observer.progress_changed(90)
        self._renderer = VideoRendererFactory.create(self.settings)
        output = project.project_directory / "output" / "final.mp4"
        return self._renderer.render(scene_paths, audio_paths, output)

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise PipelineCancelled("Cancellation requested")


def _scene_prompt(scene) -> str:
    details = [scene.director.visual_prompt, f"Camera: {scene.director.camera_motion}"]
    if scene.director.motion:
        details.append("Motion: " + ", ".join(scene.director.motion))
    if scene.director.preserve:
        details.append("Preserve: " + ", ".join(scene.director.preserve))
    return ". ".join(details)


def _scene_chunk_paths(project: VideoProject, scene_id: int, count: int) -> list[Path]:
    first = project.scene_output(scene_id)
    return [first, *[
        project.project_directory / "scenes" / f"scene_{scene_id:03d}_clip_{index:03d}.mp4"
        for index in range(2, count + 1)
    ]]
