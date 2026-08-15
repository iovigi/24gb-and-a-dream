from pathlib import Path

from core.config import load_config


def test_config_loads_and_resolves_relative_paths() -> None:
    root = Path(__file__).parents[1]
    settings = load_config(root / "config.yaml")
    assert settings.app.projects_dir == (root / "projects").resolve()
    assert settings.comfyui.http_url == "http://127.0.0.1:8188"
