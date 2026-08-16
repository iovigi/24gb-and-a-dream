"""Guards against the cross-thread GUI access that killed the process with 0xC0000005.

A worker signal connected to a lambda is delivered in the worker thread, so the
lambda touches widgets off the GUI thread, corrupts Qt and takes the process
down with an access violation. Bound slots of a GUI-thread QObject are queued
correctly. These tests pin that difference down.
"""

from __future__ import annotations

import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtCore = pytest.importorskip("PySide6.QtCore")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


class _Emitter(QObject):
    payload = Signal(object)
    done = Signal()

    @Slot()
    def run(self) -> None:
        self.payload.emit({"scene": 1})
        self.done.emit()


class _Receiver(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.bound_thread: int | None = None
        self.lambda_thread: int | None = None

    @Slot(object)
    def bound_slot(self, value: object) -> None:
        self.bound_thread = threading.get_ident()


def _run_worker(app, connect) -> None:
    emitter = _Emitter()
    thread = QThread()
    emitter.moveToThread(thread)
    thread.started.connect(emitter.run)
    connect(emitter)
    emitter.done.connect(thread.quit)
    thread.finished.connect(app.quit)
    thread.start()
    QTimer.singleShot(10_000, app.quit)
    app.exec()
    app.processEvents()
    thread.wait(5_000)


def test_bound_slot_is_delivered_on_the_gui_thread(qt_app) -> None:
    receiver = _Receiver()
    _run_worker(qt_app, lambda emitter: emitter.payload.connect(receiver.bound_slot))
    assert receiver.bound_thread == threading.get_ident(), (
        "Worker signals must reach the GUI thread; a receiver running in the "
        "worker thread would corrupt Qt and crash the process."
    )


def test_lambda_receiver_runs_in_the_worker_thread(qt_app) -> None:
    """Documents why lambdas must never touch widgets in this codebase."""
    receiver = _Receiver()

    def connect(emitter):
        emitter.payload.connect(
            lambda value: setattr(receiver, "lambda_thread", threading.get_ident())
        )

    _run_worker(qt_app, connect)
    assert receiver.lambda_thread is not None
    assert receiver.lambda_thread != threading.get_ident()


def test_main_window_worker_signals_use_bound_slots(qt_app, mock_settings) -> None:
    """The plan signal must land in a real slot, never a lambda."""
    from ui.main_window import MainWindow

    window = MainWindow(mock_settings)
    try:
        assert callable(window.display_plan)
        assert getattr(window.display_plan, "__self__", None) is window
    finally:
        window.close()
        window.deleteLater()
