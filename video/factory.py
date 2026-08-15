from core.config import Settings
from video.base import VideoGenerator
from video.mock import MockVideoGenerator
from video.wan import WanVideoGenerator


class VideoGeneratorFactory:
    @staticmethod
    def create(settings: Settings) -> VideoGenerator:
        if settings.video.backend == "mock":
            return MockVideoGenerator()
        if settings.video.backend == "wan22":
            return WanVideoGenerator(settings.comfyui)
        raise ValueError(f"Unsupported video backend: {settings.video.backend}")
