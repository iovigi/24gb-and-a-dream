from pathlib import Path

from core.requests import GenerationRequest
from llm.mock import MockLLMEngine
from render.subtitles import format_srt_timestamp, write_srt
from render.timeline import build_timeline


def test_narration_extends_timeline_and_calculates_clips() -> None:
    plan = MockLLMEngine().create_director_plan(GenerationRequest(prompt="Timeline", duration_seconds=20))
    timeline = build_timeline(plan, {1: 12.2}, clip_seconds=5)
    assert timeline[0].duration_seconds == 12.2
    assert timeline[0].clip_count == 3
    assert timeline[1].start_seconds == 12.2


def test_subtitle_timestamps_and_file(tmp_path: Path) -> None:
    plan = MockLLMEngine().create_director_plan(GenerationRequest(prompt="SRT", duration_seconds=10))
    timeline = build_timeline(plan)
    output = write_srt(timeline, tmp_path / "subtitles.srt")
    assert format_srt_timestamp(3661.234) == "01:01:01,234"
    assert "00:00:00,000 --> 00:00:10,000" in output.read_text(encoding="utf-8-sig")
