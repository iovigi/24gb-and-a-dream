from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import QCoreApplication, QThread, Qt, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QRadioButton, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from core.config import Settings
from core.pipeline import GenerationPipeline
from core.preflight import missing_requirements
from core.requests import GenerationRequest
from ui.widgets.image_picker import ImagePicker
from ui.worker import GenerationWorker
from utils.crash import note_activity
from utils.gpu import gpu_summary
from utils.logging import log_directory


_logger = logging.getLogger("dream24gb.ui")


def _on_gui_thread(context: str) -> bool:
    """Refuse to touch widgets from a worker thread.

    Qt widget access outside the GUI thread is undefined behaviour: it corrupts
    Qt's internal state and the process dies later with an access violation,
    far away from the real cause. Logging and skipping keeps the app alive and
    names the offender.
    """
    application = QCoreApplication.instance()
    if application is None or QThread.currentThread() == application.thread():
        return True
    _logger.critical(
        "BLOCKED cross-thread GUI access in %s (current thread: %s). "
        "This would have crashed the process; the update was skipped.",
        context, QThread.currentThread(),
    )
    return False


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: Settings,
        log_path: Path | None = None,
        crash_log_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.log_path = log_path or (log_directory() / "app.log")
        self.crash_log_path = crash_log_path or (log_directory() / "crash.log")
        self.logger = logging.getLogger("dream24gb.ui")
        self.thread: QThread | None = None
        self.worker: GenerationWorker | None = None
        self.output_path: Path | None = None
        self._close_when_finished = False
        self.setWindowTitle("24GB and a Dream")
        self.resize(1040, 820)
        self._build_ui()
        self._report_missing_requirements()
        self.logger.info("Main window ready")

    def _report_missing_requirements(self) -> None:
        """Say up front what is missing, rather than minutes into a generation."""
        problems = missing_requirements(self.settings)
        if not problems:
            return
        for problem in problems:
            self.logger.warning("Missing requirement: %s", problem)
        self.status_label.setText(
            f"{len(problems)} required file(s) missing — generation will fail. See the log."
        )
        self.status_label.setToolTip("\n".join(problems))

    def report_previous_crash(self) -> None:
        """Tell the user the last run died, and point at the evidence."""
        self.logger.warning("Previous session did not exit cleanly")
        self.status_label.setText("Last run ended unexpectedly — see the log for details.")
        QMessageBox.warning(
            self,
            "Previous run crashed",
            "The last session ended without shutting down cleanly.\n\n"
            f"Crash report: {self.crash_log_path}\n"
            f"Session log: {self.log_path}",
        )

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("24GB AND A DREAM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: 700; margin: 10px;")
        layout.addWidget(title)
        splitter = QSplitter()
        splitter.addWidget(self._request_panel())
        splitter.addWidget(self._result_panel())
        splitter.setSizes([560, 420])
        layout.addWidget(splitter, 1)
        self.status_label = QLabel("Ready. What happens on the 3090 Ti stays on the 3090 Ti.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        controls = QHBoxLayout()
        self.generate_button = QPushButton("GENERATE")
        self.generate_button.setMinimumHeight(42)
        self.cancel_button = QPushButton("CANCEL")
        self.cancel_button.setEnabled(False)
        self.generate_button.clicked.connect(self.start_generation)
        self.cancel_button.clicked.connect(self.cancel_generation)
        controls.addStretch()
        controls.addWidget(self.generate_button)
        controls.addWidget(self.cancel_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addLayout(controls)
        layout.addWidget(QLabel(f"GPU STATUS: {gpu_summary()}"))
        self.setCentralWidget(root)

    def _request_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("PROMPT"))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Make me something cinematic…")
        self.prompt.setMinimumHeight(120)
        layout.addWidget(self.prompt)
        layout.addWidget(QLabel("REFERENCE IMAGE (OPTIONAL)"))
        self.image_picker = ImagePicker()
        layout.addWidget(self.image_picker)
        form = QFormLayout()
        self.duration = QComboBox()
        for seconds in (10, 15, 20, 30, 45, 60):
            self.duration.addItem(f"{seconds} seconds", seconds)
        self.duration.setCurrentText("30 seconds")
        self.aspect_ratio = QComboBox()
        self.aspect_ratio.addItems(["16:9", "9:16", "1:1"])
        self.style = QComboBox()
        self.style.addItems(["cinematic", "commercial", "documentary", "anime", "photorealistic"])
        form.addRow("Duration", self.duration)
        form.addRow("Aspect ratio", self.aspect_ratio)
        form.addRow("Style", self.style)
        layout.addLayout(form)
        voice_group = QGroupBox("VOICE-OVER")
        voice_layout = QFormLayout(voice_group)
        self.voice_enabled = QCheckBox("Enable voice-over")
        self.voice_enabled.setChecked(True)
        self.language = QComboBox()
        self.language.addItem("Bulgarian", "bg")
        self.language.addItem("English", "en")
        self.voice = QComboBox()
        self.voice.addItem("Female", "female")
        self.voice.addItem("Male", "male")
        modes = QWidget()
        modes_layout = QHBoxLayout(modes)
        modes_layout.setContentsMargins(0, 0, 0, 0)
        self.auto_narration = QRadioButton("Let the AI cook")
        self.manual_narration = QRadioButton("Use my exact text")
        self.auto_narration.setChecked(True)
        modes_layout.addWidget(self.auto_narration)
        modes_layout.addWidget(self.manual_narration)
        self.narration = QPlainTextEdit()
        self.narration.setPlaceholderText("Exact narration text")
        self.narration.setEnabled(False)
        self.manual_narration.toggled.connect(self.narration.setEnabled)
        voice_layout.addRow(self.voice_enabled)
        voice_layout.addRow("Language", self.language)
        voice_layout.addRow("Voice", self.voice)
        voice_layout.addRow("Narration", modes)
        voice_layout.addRow(self.narration)
        layout.addWidget(voice_group)
        self.advanced_button = QPushButton("Advanced ›")
        self.advanced_button.setCheckable(True)
        self.advanced = QGroupBox()
        advanced_form = QFormLayout(self.advanced)
        self.seed = QSpinBox()
        self.seed.setRange(-1, 2_147_483_647)
        self.seed.setValue(-1)
        self.negative_prompt = QPlainTextEdit()
        self.negative_prompt.setMaximumHeight(60)
        self.tts_speed = QDoubleSpinBox()
        self.tts_speed.setRange(0.5, 2.0)
        self.tts_speed.setSingleStep(0.05)
        self.tts_speed.setValue(1.0)
        advanced_form.addRow("Seed (-1 = random)", self.seed)
        advanced_form.addRow("Negative prompt", self.negative_prompt)
        advanced_form.addRow("TTS speed", self.tts_speed)
        self.advanced.setVisible(False)
        self.advanced_button.toggled.connect(self.advanced.setVisible)
        layout.addWidget(self.advanced_button)
        layout.addWidget(self.advanced)
        layout.addStretch()
        return panel

    def _result_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("DIRECTOR PLAN"))
        self.plan_preview = QPlainTextEdit()
        self.plan_preview.setReadOnly(True)
        self.plan_preview.setPlaceholderText("The validated scene plan will appear here.")
        layout.addWidget(self.plan_preview, 1)
        buttons = QHBoxLayout()
        self.open_output_button = QPushButton("Open output folder")
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(self.open_output_folder)
        self.open_logs_button = QPushButton("Open logs")
        self.open_logs_button.setToolTip(str(self.log_path))
        self.open_logs_button.clicked.connect(self.open_logs_folder)
        buttons.addWidget(self.open_output_button)
        buttons.addWidget(self.open_logs_button)
        layout.addLayout(buttons)
        return panel

    def _make_request(self) -> GenerationRequest:
        return GenerationRequest(
            prompt=self.prompt.toPlainText(), reference_image=self.image_picker.path,
            duration_seconds=self.duration.currentData(), aspect_ratio=self.aspect_ratio.currentText(),
            style=self.style.currentText(), voice_enabled=self.voice_enabled.isChecked(),
            voice_language=self.language.currentData(), voice_name=self.voice.currentData(),
            narration_mode="manual" if self.manual_narration.isChecked() else "auto",
            narration_text=self.narration.toPlainText() if self.manual_narration.isChecked() else None,
            seed=self.seed.value(), negative_prompt=self.negative_prompt.toPlainText(),
            tts_speed=self.tts_speed.value(),
        )

    def start_generation(self) -> None:
        try:
            request = self._make_request()
        except ValidationError as exc:
            self.logger.warning("Invalid generation settings: %s", exc)
            QMessageBox.warning(self, "Check generation settings", exc.errors()[0]["msg"])
            return
        self.logger.info(
            "Starting generation duration=%ss aspect=%s style=%s voice=%s",
            request.duration_seconds, request.aspect_ratio, request.style, request.voice_enabled,
        )
        note_activity("generation requested")
        self.generate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.open_output_button.setEnabled(False)
        self.progress.setValue(0)
        pipeline = GenerationPipeline(self.settings)
        self.worker = GenerationWorker(pipeline, request)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        # Every worker signal must reach the GUI thread through the event loop.
        # A lambda receiver has no thread affinity, so PySide6 runs it in the
        # worker thread; touching a widget from there corrupts Qt and kills the
        # process with an access violation. Bound slots plus an explicit queued
        # connection keep all widget access on the GUI thread.
        queued = Qt.ConnectionType.QueuedConnection
        self.worker.status.connect(self.status_label.setText, queued)
        self.worker.progress.connect(self.progress.setValue, queued)
        self.worker.plan.connect(self.display_plan, queued)
        self.worker.completed.connect(self.generation_completed, queued)
        self.worker.failed.connect(self.generation_failed, queued)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._worker_finished)
        self.thread.start()

    def cancel_generation(self) -> None:
        if self.worker:
            self.status_label.setText("Cancelling safely; completed scenes will be kept…")
            self.worker.cancel()
            self.cancel_button.setEnabled(False)

    @Slot(object)
    def display_plan(self, plan) -> None:
        if not _on_gui_thread("display_plan"):
            return
        self.plan_preview.setPlainText(plan.model_dump_json(indent=2))

    @Slot(str)
    def generation_completed(self, output: str) -> None:
        if not _on_gui_thread("generation_completed"):
            return
        self.logger.info("Generation completed: %s", output)
        note_activity("generation completed")
        self.output_path = Path(output)
        self.open_output_button.setEnabled(True)

    @Slot(str)
    def generation_failed(self, message: str) -> None:
        if not _on_gui_thread("generation_failed"):
            return
        self.logger.error("Generation stopped: %s", message)
        note_activity("generation failed")
        self.status_label.setText(message)
        if not message.lower().startswith("generation cancelled"):
            QMessageBox.critical(
                self, "Generation stopped", f"{message}\n\nFull log: {self.log_path}"
            )

    @Slot()
    def _worker_finished(self) -> None:
        if not _on_gui_thread("_worker_finished"):
            return
        self.logger.info("Worker thread finished")
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.thread = None
        self.worker = None
        if self._close_when_finished:
            self.close()

    def open_output_folder(self) -> None:
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_path.parent)))

    def open_logs_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_path.parent)))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.logger.info("Close requested (generation running=%s)", self.worker is not None)
        if self.worker:
            self.worker.cancel()
            self._close_when_finished = True
            self.status_label.setText("Cancelling safely before closing…")
            event.ignore()
            return
        event.accept()
