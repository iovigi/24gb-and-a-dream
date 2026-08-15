from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(project_directory: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("dream24gb")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    if project_directory:
        log_path = project_directory / "logs" / "generation.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger
