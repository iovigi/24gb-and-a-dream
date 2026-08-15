from __future__ import annotations

import json
import subprocess
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from core.config import FFmpegConfig


class VideoRenderer(ABC):
    @abstractmethod
    def render(self, scene_paths: list[Path], audio_paths: list[Path], output_path: Path) -> Path:
        raise NotImplementedError

    def cancel(self) -> None:
        """Stop an in-progress render if supported."""


class MockVideoRenderer(VideoRenderer):
    def render(self, scene_paths: list[Path], audio_paths: list[Path], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({
            "mock_final_video": True,
            "scenes": [str(path) for path in scene_paths],
            "audio": [str(path) for path in audio_paths],
        }, indent=2), encoding="utf-8")
        return output_path


class FFmpegVideoRenderer(VideoRenderer):
    def __init__(self, config: FFmpegConfig) -> None:
        self.config = config
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def render(self, scene_paths: list[Path], audio_paths: list[Path], output_path: Path) -> Path:
        if not scene_paths:
            raise ValueError("At least one video scene is required")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        video_list = output_path.parent / "video_concat.txt"
        _write_concat_file(video_list, scene_paths)
        video_input = output_path.parent / "joined_video.mp4"
        self._run([
            self.config.binary, "-y", "-f", "concat", "-safe", "0", "-i", str(video_list),
            "-c", "copy", str(video_input),
        ])
        inputs = ["-i", str(video_input)]
        audio_input: Path | None = None
        if audio_paths:
            audio_list = output_path.parent / "audio_concat.txt"
            _write_concat_file(audio_list, audio_paths)
            audio_input = output_path.parent / "joined_audio.wav"
            self._run([
                self.config.binary, "-y", "-f", "concat", "-safe", "0", "-i", str(audio_list),
                "-af", "loudnorm=I=-16:LRA=11:TP=-1.5", str(audio_input),
            ])
            inputs.extend(["-i", str(audio_input)])
        command = [self.config.binary, "-y", *inputs, "-c:v", self.config.encoder, "-pix_fmt", "yuv420p"]
        if audio_input:
            command.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            command.append("-an")
        command.extend(["-movflags", "+faststart", str(output_path)])
        try:
            self._run(command)
        except RuntimeError:
            fallback = [self.config.fallback_encoder if item == self.config.encoder else item for item in command]
            self._run(fallback)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg did not produce a final video")
        return output_path

    def _run(self, command: list[str]) -> None:
        try:
            with self._lock:
                self._process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            _, stderr = self._process.communicate()
            if self._process.returncode:
                tail = "\n".join(stderr.splitlines()[-20:])
                raise RuntimeError(f"FFmpeg failed with exit code {self._process.returncode}:\n{tail}")
        except FileNotFoundError as exc:
            raise RuntimeError(f"FFmpeg was not found: {self.config.binary}") from exc
        finally:
            with self._lock:
                self._process = None

    def cancel(self) -> None:
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()


def _write_concat_file(path: Path, inputs: list[Path]) -> None:
    lines = [f"file '{str(item.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for item in inputs]
    path.write_text("\n".join(lines), encoding="utf-8")
