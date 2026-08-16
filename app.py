from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> int:
    root = application_root()

    # Logging and crash capture are installed before anything else is imported,
    # so even an import-time failure of PySide6/torch leaves a full traceback.
    from utils.crash import install as install_crash_handlers
    from utils.crash import log_exception, note_activity, previous_session_crashed
    from utils.logging import configure_app_logging

    log_path = configure_app_logging(root)
    crash_path = install_crash_handlers(root)
    logger = logging.getLogger("dream24gb")
    logger.info("Central log: %s", log_path)
    logger.info("Crash log:   %s", crash_path)
    crashed_before = previous_session_crashed()

    parser = argparse.ArgumentParser(description="24GB and a Dream")
    parser.add_argument("--config", type=Path, default=root / "config.yaml")
    parser.add_argument("--debug", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--selftest", action="store_true",
        help="Build the window, verify imports and config, then exit without showing it",
    )
    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("dream24gb").setLevel(logging.DEBUG)

    try:
        note_activity("importing Qt and application modules")
        from PySide6.QtWidgets import QApplication, QMessageBox

        from core.config import load_config
        from ui.main_window import MainWindow
        from utils.crash import install_qt_message_handler
    except Exception as exc:
        log_exception(exc, "Failed to import application modules")
        return 3

    note_activity("creating QApplication")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("24GB and a Dream")
    install_qt_message_handler()

    try:
        note_activity(f"loading config {args.config}")
        settings = load_config(args.config)
    except Exception as exc:
        log_exception(exc, f"Configuration error while loading {args.config}")
        QMessageBox.critical(None, "Configuration error", f"{exc}\n\nDetails: {log_path}")
        return 2

    try:
        note_activity("building main window")
        window = MainWindow(settings, log_path=log_path, crash_log_path=crash_path)
        if args.selftest:
            # Proves the packaged app can import every module, load its Qt
            # plugins and read the config. Used by build.ps1 to fail a broken
            # build instead of shipping one that dies on the user's desktop.
            logger.info("Self-test passed: modules, Qt plugins and config are usable")
            window.deleteLater()
            return 0
        if crashed_before:
            window.report_previous_crash()
        window.show()
        note_activity("event loop running")
        code = app.exec()
        logger.info("Qt event loop exited with code %s", code)
        return code
    except Exception as exc:
        log_exception(exc, "Fatal error in the main window")
        QMessageBox.critical(
            None, "24GB and a Dream crashed", f"{exc}\n\nFull details: {crash_path}"
        )
        return 1
    finally:
        # Release the VRAM of a ComfyUI this app started; one that was already
        # running is left alone.
        if settings.comfyui.stop_on_exit:
            try:
                from video.comfy_launcher import stop_shared_launcher

                stop_shared_launcher()
            except Exception as exc:  # shutdown must never mask the real result
                logger.warning("Could not stop ComfyUI: %s", exc)


if __name__ == "__main__":
    raise SystemExit(main())
