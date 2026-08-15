from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AppConfig(StrictModel):
    projects_dir: Path = Path("./projects")
    mock_mode: bool = True
    max_scene_retries: int = Field(default=2, ge=0, le=10)
    min_free_disk_gb: float = Field(default=2.0, ge=0)


class GPUConfig(StrictModel):
    auto_unload: bool = True
    preferred_device: str = "cuda"


class LLMConfig(StrictModel):
    backend: str = "mock"
    model_path: Path = Path("./models/qwen.gguf")
    executable: Path = Path("./runtime/llama.cpp/llama-cli.exe")
    context_size: int = Field(default=16384, ge=1024)
    predict_tokens: int = Field(default=4096, ge=256)
    gpu_layers: int = -1


class ComfyUIConfig(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8188, ge=1, le=65535)
    workflows_dir: Path = Path("./workflows")
    timeout_seconds: int = Field(default=3600, ge=1)

    @property
    def http_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"


class VideoConfig(StrictModel):
    backend: str = "mock"
    default_width: int = Field(default=1280, ge=64)
    default_height: int = Field(default=720, ge=64)
    default_fps: int = Field(default=24, ge=1, le=120)
    default_steps: int = Field(default=20, ge=1)
    default_cfg: float = Field(default=6.0, ge=0)
    clip_seconds: float = Field(default=5.0, gt=0)


class TTSLanguageConfig(StrictModel):
    backend: str = "mock"
    model_path: Path
    command: list[str] = Field(default_factory=list)


class TTSConfig(StrictModel):
    default_language: str = "bg"
    bg: TTSLanguageConfig
    en: TTSLanguageConfig


class FFmpegConfig(StrictModel):
    binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    encoder: str = "h264_nvenc"
    fallback_encoder: str = "libx264"


class Settings(StrictModel):
    app: AppConfig
    gpu: GPUConfig
    llm: LLMConfig
    comfyui: ComfyUIConfig
    video: VideoConfig
    tts: TTSConfig
    ffmpeg: FFmpegConfig
    root_dir: Path = Field(default=Path.cwd(), exclude=True)

    @model_validator(mode="after")
    def resolve_paths(self) -> "Settings":
        def resolved(path: Path) -> Path:
            return path if path.is_absolute() else (self.root_dir / path).resolve()

        self.app.projects_dir = resolved(self.app.projects_dir)
        self.llm.model_path = resolved(self.llm.model_path)
        self.llm.executable = resolved(self.llm.executable)
        self.comfyui.workflows_dir = resolved(self.comfyui.workflows_dir)
        self.tts.bg.model_path = resolved(self.tts.bg.model_path)
        self.tts.en.model_path = resolved(self.tts.en.model_path)
        return self


def load_config(path: str | Path = "config.yaml") -> Settings:
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream) or {}
    return Settings.model_validate({**raw, "root_dir": config_path.parent})
