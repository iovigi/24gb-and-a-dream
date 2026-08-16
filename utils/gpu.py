from __future__ import annotations

import functools
import gc
import importlib
import subprocess
from typing import Any

NO_GPU = "CUDA GPU not detected"


def release_gpu_memory(*objects: Any) -> None:
    del objects
    gc.collect()
    try:
        torch = importlib.import_module("to" + "rch")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


@functools.lru_cache(maxsize=1)
def gpu_summary() -> str:
    """Describe the GPU without depending on torch.

    Inference happens in other processes (ComfyUI's virtual environment and
    llama.cpp), so this process often has no CUDA-enabled torch at all - a
    CPU-only build reports no GPU, and the packaged app excludes torch
    entirely. nvidia-smi ships with the driver and always tells the truth.
    """
    return _nvidia_smi_summary() or _torch_summary() or NO_GPU


def _nvidia_smi_summary() -> str | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    line = next((item.strip() for item in result.stdout.splitlines() if item.strip()), "")
    name, _, memory = line.partition(",")
    if not name:
        return None
    try:
        gigabytes = float(memory.strip()) / 1024
    except ValueError:
        return name.strip()
    return f"{name.strip()} ({gigabytes:.1f} GB VRAM)"


def _torch_summary() -> str | None:
    try:
        torch = importlib.import_module("to" + "rch")
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return f"{props.name} ({props.total_memory / 1024**3:.1f} GB VRAM)"
    except ImportError:
        pass
    return None
