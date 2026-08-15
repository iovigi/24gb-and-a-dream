from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from core.config import load_config
from ui.main_window import MainWindow


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="24GB and a Dream")
    parser.add_argument("--config", type=Path, default=application_root() / "config.yaml")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("24GB and a Dream")
    try:
        settings = load_config(args.config)
    except Exception as exc:
        QMessageBox.critical(None, "Configuration error", str(exc))
        return 2
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
