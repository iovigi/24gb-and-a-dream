"""Up-front validation of everything a real generation needs on disk.

Without this the first missing file surfaces only after the director plan has
run, minutes in, as a bare FileNotFoundError. The packaged build makes that easy
to hit: relative paths in config.yaml resolve against the config's own folder,
so a dist/ that lacks runtime/ and models/ looks fine until generation starts.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from core.config import Settings, TTSLanguageConfig
from core.requests import GenerationRequest


class PreflightError(RuntimeError):
    """Raised with every missing requirement at once, not just the first."""


def missing_requirements(
    settings: Settings, request: GenerationRequest | None = None
) -> list[str]:
    """Describe everything the configured backends need but cannot find."""
    problems: list[str] = []
    if settings.app.mock_mode:
        return problems
    problems.extend(_llm_problems(settings))
    problems.extend(_tts_problems(settings, request))
    problems.extend(_video_problems(settings))
    problems.extend(_ffmpeg_problems(settings))
    return problems


def check(settings: Settings, request: GenerationRequest | None = None) -> None:
    problems = missing_requirements(settings, request)
    if not problems:
        return
    listed = "\n".join(f"  - {problem}" for problem in problems)
    raise PreflightError(
        f"{len(problems)} required file(s) or service(s) are missing:\n{listed}\n\n"
        "Relative paths in config.yaml resolve against the folder holding that file."
    )


def _llm_problems(settings: Settings) -> list[str]:
    problems: list[str] = []
    backend = settings.llm.backend
    if backend == "mock":
        return problems
    if backend == "llama_cpp_cli":
        server = settings.llm.executable.with_name("llama-server.exe")
        if not server.is_file():
            problems.append(f"llama.cpp server is missing: {server}")
    if backend in {"llama_cpp_cli", "llama_cpp"} and not settings.llm.model_path.is_file():
        problems.append(f"LLM model is missing: {settings.llm.model_path}")
    return problems


def _tts_problems(settings: Settings, request: GenerationRequest | None) -> list[str]:
    if request is not None and not request.voice_enabled:
        return []
    language = request.voice_language if request is not None else settings.tts.default_language
    config = settings.tts.bg if language == "bg" else settings.tts.en
    return _tts_language_problems(config, language)


def _tts_language_problems(config: TTSLanguageConfig, language: str) -> list[str]:
    if config.backend == "mock":
        return []
    problems: list[str] = []
    if not config.command:
        problems.append(f"No {language} TTS command is configured")
    else:
        # The runtime hands this straight to subprocess, which resolves a
        # relative path against the current directory - check it the same way.
        executable = Path(config.command[0])
        if not executable.is_file():
            problems.append(f"{language} TTS runtime is missing: {executable.resolve()}")
    if not config.model_path.is_dir():
        problems.append(f"{language} TTS voices are missing: {config.model_path}")
    return problems


def _video_problems(settings: Settings) -> list[str]:
    if settings.video.backend == "mock":
        return []
    problems: list[str] = []
    if not settings.comfyui.workflows_dir.is_dir():
        problems.append(f"ComfyUI workflows are missing: {settings.comfyui.workflows_dir}")
    if settings.comfyui.autostart:
        if not settings.comfyui.python.is_file():
            problems.append(f"ComfyUI runtime is missing: {settings.comfyui.python}")
        elif not (settings.comfyui.root / "main.py").is_file():
            problems.append(f"ComfyUI main.py is missing: {settings.comfyui.root / 'main.py'}")
    return problems


def _ffmpeg_problems(settings: Settings) -> list[str]:
    problems: list[str] = []
    for label, binary in (("FFmpeg", settings.ffmpeg.binary), ("FFprobe", settings.ffmpeg.ffprobe_binary)):
        if not shutil.which(binary):
            problems.append(f"{label} is missing: {Path(binary).resolve()}")
    return problems
