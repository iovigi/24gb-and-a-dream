from __future__ import annotations

from pathlib import Path

import pytest

from core.config import Settings
from core.preflight import PreflightError, check, missing_requirements
from core.requests import GenerationRequest


def test_mock_settings_need_nothing(mock_settings: Settings) -> None:
    assert missing_requirements(mock_settings) == []


def test_missing_llama_server_and_model_are_both_reported(mock_settings: Settings, tmp_path: Path) -> None:
    mock_settings.app.mock_mode = False
    mock_settings.llm.backend = "llama_cpp_cli"
    mock_settings.llm.executable = tmp_path / "llama.cpp" / "llama-cli.exe"
    mock_settings.llm.model_path = tmp_path / "models" / "qwen.gguf"

    problems = missing_requirements(mock_settings, _request(voice_enabled=False))

    assert any("llama.cpp server is missing" in problem for problem in problems)
    assert any("LLM model is missing" in problem for problem in problems)


def test_present_llama_server_is_not_reported(mock_settings: Settings, tmp_path: Path) -> None:
    server = tmp_path / "llama.cpp" / "llama-server.exe"
    server.parent.mkdir(parents=True)
    server.write_bytes(b"")
    model = tmp_path / "qwen.gguf"
    model.write_bytes(b"")
    mock_settings.app.mock_mode = False
    mock_settings.llm.backend = "llama_cpp_cli"
    mock_settings.llm.executable = server.with_name("llama-cli.exe")
    mock_settings.llm.model_path = model

    problems = missing_requirements(mock_settings, _request(voice_enabled=False))

    assert not any("llama" in problem.lower() for problem in problems)


def test_disabled_voice_skips_tts_checks(mock_settings: Settings, tmp_path: Path) -> None:
    mock_settings.app.mock_mode = False
    mock_settings.tts.bg.backend = "local"
    mock_settings.tts.bg.command = [str(tmp_path / "missing-python.exe")]
    mock_settings.tts.bg.model_path = tmp_path / "voices"

    with_voice = missing_requirements(mock_settings, _request(voice_enabled=True))
    without_voice = missing_requirements(mock_settings, _request(voice_enabled=False))

    assert any("TTS" in problem for problem in with_voice)
    assert not any("TTS" in problem for problem in without_voice)


def test_check_raises_listing_every_problem(mock_settings: Settings, tmp_path: Path) -> None:
    mock_settings.app.mock_mode = False
    mock_settings.llm.backend = "llama_cpp_cli"
    mock_settings.llm.executable = tmp_path / "llama-cli.exe"
    mock_settings.llm.model_path = tmp_path / "qwen.gguf"

    with pytest.raises(PreflightError) as error:
        check(mock_settings, _request(voice_enabled=False))

    message = str(error.value)
    assert "llama.cpp server is missing" in message
    assert "LLM model is missing" in message


def _request(voice_enabled: bool) -> GenerationRequest:
    return GenerationRequest(
        prompt="a preflight check", duration_seconds=10, voice_enabled=voice_enabled,
    )
