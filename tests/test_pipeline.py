import json

from core.pipeline import GenerationPipeline
from core.requests import GenerationRequest


def test_mock_pipeline_runs_end_to_end(mock_settings) -> None:
    request = GenerationRequest(
        prompt="A premium car reveal", duration_seconds=10,
        narration_mode="manual", narration_text="The future does not wait.", voice_language="en",
    )
    output = GenerationPipeline(mock_settings).run(request)
    assert output.is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mock_final_video"] is True
    assert len(payload["scenes"]) == 2
    project_dir = output.parents[1]
    assert (project_dir / "audio" / "scene_001.wav").is_file()
    assert (project_dir / "subtitles" / "subtitles.srt").is_file()
    assert (project_dir / "logs" / "generation.log").is_file()
