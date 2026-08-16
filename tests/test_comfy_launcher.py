from __future__ import annotations

from pathlib import Path

import pytest

from core.config import ComfyUIConfig
from video.comfy_launcher import ComfyUILauncher, ComfyUINotStarted


def _config(tmp_path: Path, **overrides) -> ComfyUIConfig:
    values = {
        "python": tmp_path / "ComfyUI" / ".venv" / "Scripts" / "python.exe",
        "root": tmp_path / "ComfyUI",
        "startup_timeout_seconds": 1,
    }
    values.update(overrides)
    return ComfyUIConfig(**values)


def test_a_running_instance_is_never_started_or_stopped(tmp_path: Path, monkeypatch) -> None:
    launcher = ComfyUILauncher(_config(tmp_path))
    monkeypatch.setattr(launcher, "is_running", lambda: True)
    started = {"called": False}
    monkeypatch.setattr(launcher, "_start", lambda: started.__setitem__("called", True))

    assert launcher.ensure_running() is False, "must report that it did not start ComfyUI"
    assert not started["called"]
    assert not launcher.started_by_us

    launcher.stop()  # must not raise, and must not touch a foreign instance


def test_autostart_disabled_explains_itself(tmp_path: Path, monkeypatch) -> None:
    launcher = ComfyUILauncher(_config(tmp_path, autostart=False))
    monkeypatch.setattr(launcher, "is_running", lambda: False)

    with pytest.raises(ComfyUINotStarted) as error:
        launcher.ensure_running()

    assert "autostart is disabled" in str(error.value)


def test_missing_runtime_is_reported_with_its_path(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    launcher = ComfyUILauncher(config)
    monkeypatch.setattr(launcher, "is_running", lambda: False)

    with pytest.raises(ComfyUINotStarted) as error:
        launcher.ensure_running()

    assert str(config.python) in str(error.value)


def test_missing_main_script_is_reported(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    config.python.parent.mkdir(parents=True)
    config.python.write_bytes(b"")
    launcher = ComfyUILauncher(config)
    monkeypatch.setattr(launcher, "is_running", lambda: False)

    with pytest.raises(ComfyUINotStarted) as error:
        launcher.ensure_running()

    assert "main.py is missing" in str(error.value)


def test_stop_is_a_noop_when_nothing_was_started(tmp_path: Path) -> None:
    ComfyUILauncher(_config(tmp_path)).stop()


def test_unreachable_endpoint_reports_not_running(tmp_path: Path) -> None:
    # Port 1 is reserved and never serves HTTP.
    launcher = ComfyUILauncher(_config(tmp_path, port=1))
    assert launcher.is_running() is False
