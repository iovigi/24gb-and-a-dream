from __future__ import annotations

import subprocess

from utils import gpu


def _clear_cache() -> None:
    gpu.gpu_summary.cache_clear()


def _result(returncode: int, stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_reports_the_gpu_from_nvidia_smi(monkeypatch) -> None:
    _clear_cache()
    monkeypatch.setattr(
        gpu.subprocess, "run", lambda *a, **k: _result(0, "NVIDIA GeForce RTX 3090 Ti, 24564\n")
    )
    assert gpu.gpu_summary() == "NVIDIA GeForce RTX 3090 Ti (24.0 GB VRAM)"
    _clear_cache()


def test_falls_back_when_nvidia_smi_is_absent(monkeypatch) -> None:
    _clear_cache()

    def missing(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(gpu.subprocess, "run", missing)
    monkeypatch.setattr(gpu, "_torch_summary", lambda: None)
    assert gpu.gpu_summary() == gpu.NO_GPU
    _clear_cache()


def test_a_cpu_only_torch_does_not_hide_the_gpu(monkeypatch) -> None:
    """The bug: torch 2.9.1+cpu reported no GPU on a machine with a 3090 Ti."""
    _clear_cache()
    monkeypatch.setattr(
        gpu.subprocess, "run", lambda *a, **k: _result(0, "NVIDIA GeForce RTX 3090 Ti, 24564\n")
    )
    monkeypatch.setattr(gpu, "_torch_summary", lambda: None)
    assert gpu.gpu_summary() != gpu.NO_GPU
    _clear_cache()


def test_nonzero_exit_is_treated_as_no_gpu(monkeypatch) -> None:
    _clear_cache()
    monkeypatch.setattr(gpu.subprocess, "run", lambda *a, **k: _result(9, ""))
    monkeypatch.setattr(gpu, "_torch_summary", lambda: None)
    assert gpu.gpu_summary() == gpu.NO_GPU
    _clear_cache()


def test_unparsable_memory_still_names_the_gpu(monkeypatch) -> None:
    _clear_cache()
    monkeypatch.setattr(gpu.subprocess, "run", lambda *a, **k: _result(0, "NVIDIA Weird Card, N/A\n"))
    assert gpu.gpu_summary() == "NVIDIA Weird Card"
    _clear_cache()
