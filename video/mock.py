from __future__ import annotations

import json
from pathlib import Path

from video.base import VideoGenerationRequest, VideoGenerator


class MockVideoGenerator(VideoGenerator):
    def _generate(self, request: VideoGenerationRequest, mode: str) -> Path:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"mock_video": True, "mode": mode, **request.model_dump(mode="json")}
        request.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return request.output_path

    def text_to_video(self, request: VideoGenerationRequest) -> Path:
        return self._generate(request, "text_to_video")

    def image_to_video(self, request: VideoGenerationRequest) -> Path:
        if request.reference_image is None:
            raise ValueError("Image-to-video requires a reference image")
        return self._generate(request, "image_to_video")
