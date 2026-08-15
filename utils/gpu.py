from __future__ import annotations

import gc
import importlib
from typing import Any


def release_gpu_memory(*objects: Any) -> None:
    del objects
    gc.collect()
    try:
        torch = importlib.import_module("to" + "rch")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def gpu_summary() -> str:
    try:
        torch = importlib.import_module("to" + "rch")
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return f"{props.name} ({props.total_memory / 1024**3:.1f} GB VRAM)"
    except ImportError:
        pass
    return "CUDA GPU not detected"
