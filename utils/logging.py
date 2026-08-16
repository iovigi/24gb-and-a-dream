from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOGGER_NAME = "dream24gb"
_FORMAT = "%(asctime)s | %(levelname)-8s | %(threadName)-14s | %(name)s | %(message)s"
_PROJECT_HANDLER_TAG = "project-log"


def log_directory(root: Path | None = None) -> Path:
    """Central log directory next to the application (or executable when frozen)."""
    if root is None:
        if getattr(sys, "frozen", False):
            root = Path(sys.executable).resolve().parent
        else:
            root = Path(__file__).resolve().parent.parent
    directory = root / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def configure_app_logging(root: Path | None = None, level: int = logging.INFO) -> Path:
    """Install the central rotating log used by every module for the whole session.

    Returns the path of the main log file.
    """
    directory = log_directory(root)
    log_path = directory / "app.log"
    formatter = logging.Formatter(_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=8 * 1024 * 1024, backupCount=5, encoding="utf-8", delay=False,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        console.setLevel(level)
        root_logger.addHandler(console)

    # Third-party libraries stay at WARNING so the log remains readable.
    for noisy in ("urllib3", "requests", "websocket", "asyncio", "PIL", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.captureWarnings(True)
    logging.getLogger(LOGGER_NAME).setLevel(level)
    return log_path


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(LOGGER_NAME if name is None else f"{LOGGER_NAME}.{name}")


def attach_project_log(project_directory: Path) -> logging.Logger:
    """Mirror the session log into the project folder without touching central handlers."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if getattr(handler, "_tag", None) == _PROJECT_HANDLER_TAG:
            logger.removeHandler(handler)
            handler.close()
    log_path = project_directory / "logs" / "generation.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    file_handler._tag = _PROJECT_HANDLER_TAG  # type: ignore[attr-defined]
    logger.addHandler(file_handler)
    logger.info("Project log attached: %s", log_path)
    return logger


def detach_project_log() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if getattr(handler, "_tag", None) == _PROJECT_HANDLER_TAG:
            logger.removeHandler(handler)
            handler.close()


def configure_logging(project_directory: Path | None = None) -> logging.Logger:
    """Backwards-compatible entry point used by the pipeline."""
    if project_directory is not None:
        return attach_project_log(project_directory)
    return logging.getLogger(LOGGER_NAME)
