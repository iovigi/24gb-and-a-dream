from __future__ import annotations

import shutil
from pathlib import Path


def ensure_free_disk_space(path: Path, minimum_gb: float) -> None:
    path.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(path).free / 1024**3
    if free < minimum_gb:
        raise RuntimeError(f"Not enough disk space: {free:.1f} GB free, {minimum_gb:.1f} GB required")


def resolution_for_aspect_ratio(aspect_ratio: str, width: int, height: int) -> tuple[int, int]:
    if aspect_ratio == "9:16":
        return height, width
    if aspect_ratio == "1:1":
        side = min(width, height)
        return side, side
    return width, height
