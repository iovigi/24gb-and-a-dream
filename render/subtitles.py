from __future__ import annotations

from pathlib import Path

from render.timeline import SceneTiming


def format_srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(timings: list[SceneTiming], output_path: Path) -> Path:
    blocks: list[str] = []
    index = 1
    for timing in timings:
        if not timing.narration_text.strip():
            continue
        blocks.append(
            f"{index}\n{format_srt_timestamp(timing.start_seconds)} --> "
            f"{format_srt_timestamp(timing.end_seconds)}\n{timing.narration_text.strip()}\n"
        )
        index += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(blocks), encoding="utf-8-sig")
    return output_path
