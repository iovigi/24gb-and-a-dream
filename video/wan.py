from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from core.config import ComfyUIConfig
from video.base import VideoGenerationRequest, VideoGenerator
from video.comfyui_client import ComfyUIClient, ComfyUIError


class WanVideoGenerator(VideoGenerator):
    def __init__(self, config: ComfyUIConfig, client: ComfyUIClient | None = None) -> None:
        self.config = config
        self.client = client or ComfyUIClient(config)
        self.cancel_event = threading.Event()

    def _load_workflow(self, name: str) -> dict[str, Any]:
        path = self.config.workflows_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"ComfyUI workflow not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _generate(self, request: VideoGenerationRequest, workflow_name: str) -> Path:
        self.cancel_event.clear()
        workflow = self._load_workflow(workflow_name)
        values: dict[str, Any] = {
            "PROMPT": request.prompt, "NEGATIVE_PROMPT": request.negative_prompt,
            "SEED": request.seed, "WIDTH": request.width, "HEIGHT": request.height,
            # Wan video latents require a 4n+1 frame count. Five seconds at 24 fps is 121 frames.
            "FRAMES": max(1, ((round(request.duration_seconds * request.fps) + 3) // 4) * 4 + 1),
            "FPS": request.fps, "STEPS": request.steps, "CFG": request.cfg,
        }
        if request.reference_image:
            values["REFERENCE_IMAGE"] = self.client.upload_image(request.reference_image)
        patched = _replace_placeholders(copy.deepcopy(workflow), values)
        prompt_id = self.client.submit_workflow(patched)
        job = self.client.wait_for_completion(prompt_id, self.cancel_event)
        outputs = self.client.get_outputs(job)
        if not outputs:
            raise ComfyUIError(f"ComfyUI job {prompt_id} produced no discoverable outputs")
        return self.client.download_output(outputs[-1], request.output_path)

    def text_to_video(self, request: VideoGenerationRequest) -> Path:
        return self._generate(request, "wan22_t2v.json")

    def image_to_video(self, request: VideoGenerationRequest) -> Path:
        if not request.reference_image:
            raise ValueError("Image-to-video requires a reference image")
        return self._generate(request, "wan22_i2v.json")

    def cancel(self) -> None:
        self.cancel_event.set()
        self.client.cancel()


def _replace_placeholders(value: Any, parameters: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_placeholders(item, parameters) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_placeholders(item, parameters) for item in value]
    if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
        key = value[2:-2]
        if key not in parameters:
            raise ValueError(f"Workflow placeholder has no value: {key}")
        return parameters[key]
    return value
