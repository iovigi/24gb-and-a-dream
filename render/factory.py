from core.config import Settings
from render.ffmpeg import FFmpegVideoRenderer, MockVideoRenderer, VideoRenderer


class VideoRendererFactory:
    @staticmethod
    def create(settings: Settings) -> VideoRenderer:
        return MockVideoRenderer() if settings.app.mock_mode else FFmpegVideoRenderer(settings.ffmpeg)
