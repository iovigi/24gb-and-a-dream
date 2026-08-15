from __future__ import annotations

from pathlib import Path

import pytest

from core.config import Settings, load_config


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    settings = load_config(Path(__file__).parents[1] / "config.yaml")
    settings.app.projects_dir = tmp_path / "projects"
    settings.app.min_free_disk_gb = 0
    settings.app.mock_mode = True
    settings.llm.backend = "mock"
    settings.video.backend = "mock"
    settings.tts.bg.backend = "mock"
    settings.tts.en.backend = "mock"
    return settings
