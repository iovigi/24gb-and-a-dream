from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from make_dist_config import rewrite  # noqa: E402


def _config() -> dict:
    return {
        "app": {"projects_dir": "./projects"},
        "comfyui": {"workflows_dir": "./workflows"},
        "llm": {"model_path": "./models/llm/qwen.gguf", "executable": "./runtime/llama.cpp/llama-cli.exe"},
        "tts": {
            "bg": {
                "model_path": "./models/tts",
                "command": ["./runtime/tts/.venv/Scripts/python.exe", "./tts/piper_runner.py",
                            "--language", "{language}", "--text", "{text}"],
            },
            "en": {"model_path": "./models/tts", "command": []},
        },
        "ffmpeg": {"binary": "./runtime/ffmpeg/ffmpeg.exe", "ffprobe_binary": "./runtime/ffmpeg/ffprobe.exe"},
    }


def test_repository_paths_become_absolute(tmp_path: Path) -> None:
    config = _config()
    rewrite(config, tmp_path)

    assert Path(config["llm"]["model_path"]).is_absolute()
    assert Path(config["llm"]["executable"]).is_absolute()
    assert Path(config["ffmpeg"]["binary"]).is_absolute()
    assert Path(config["ffmpeg"]["ffprobe_binary"]).is_absolute()
    assert Path(config["tts"]["bg"]["model_path"]).is_absolute()


def test_deployment_local_paths_stay_relative(tmp_path: Path) -> None:
    config = _config()
    rewrite(config, tmp_path)

    assert config["app"]["projects_dir"] == "./projects"
    assert config["comfyui"]["workflows_dir"] == "./workflows"


def test_command_rewrites_only_existing_files(tmp_path: Path) -> None:
    runner = tmp_path / "tts" / "piper_runner.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("", encoding="utf-8")
    config = _config()

    rewrite(config, tmp_path)
    command = config["tts"]["bg"]["command"]

    assert Path(command[1]).is_absolute(), "an existing repository file must be absolute"
    assert command[0] == "./runtime/tts/.venv/Scripts/python.exe", "a missing file is left alone"
    assert command[2:] == ["--language", "{language}", "--text", "{text}"], "flags and placeholders survive"


def test_absolute_paths_are_left_alone(tmp_path: Path) -> None:
    config = _config()
    config["llm"]["model_path"] = str(tmp_path / "already" / "absolute.gguf")

    rewrite(config, tmp_path)

    assert config["llm"]["model_path"] == str(tmp_path / "already" / "absolute.gguf")


def test_output_is_valid_yaml_round_trip(tmp_path: Path) -> None:
    config = _config()
    rewrite(config, tmp_path)

    reloaded = yaml.safe_load(yaml.safe_dump(config, sort_keys=False))

    assert reloaded == config
