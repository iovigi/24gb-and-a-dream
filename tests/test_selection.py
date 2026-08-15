from pathlib import Path

from core.requests import GenerationRequest
from tts.factory import TTSEngineFactory
from tts.mock import MockTTSEngine


def test_t2v_and_i2v_mode_selection(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"placeholder")
    assert GenerationRequest(prompt="No image").video_mode == "text_to_video"
    assert GenerationRequest(prompt="Image", reference_image=image).video_mode == "image_to_video"


def test_bg_and_en_tts_selection(mock_settings) -> None:
    assert isinstance(TTSEngineFactory.create(mock_settings.tts, "bg"), MockTTSEngine)
    assert isinstance(TTSEngineFactory.create(mock_settings.tts, "en"), MockTTSEngine)
