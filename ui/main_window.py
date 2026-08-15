from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QRadioButton, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from core.config import Settings
from core.pipeline import GenerationPipeline
from core.requests import GenerationRequest
from ui.widgets.image_picker import ImagePicker
from ui.worker import GenerationWorker
from utils.gpu import gpu_summary


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.thread: QThread | None = None
        self.worker: GenerationWorker | None = None
        self.output_path: Path | None = None
        self._close_when_finished = False
        self.setWindowTitle("24GB and a Dream")
        self.resize(1040, 820)
        self._build_ui()

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
        self.open_output_button = QPushButton("Open output folder")
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(self.open_output_folder)
        layout.addWidget(self.open_output_button)
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
            QMessageBox.warning(self, "Check generation settings", exc.errors()[0]["msg"])
            return
        self.generate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.open_output_button.setEnabled(False)
        self.progress.setValue(0)
        pipeline = GenerationPipeline(self.settings)
        self.worker = GenerationWorker(pipeline, request)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status_label.setText)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.plan.connect(lambda plan: self.plan_preview.setPlainText(plan.model_dump_json(indent=2)))
        self.worker.completed.connect(self.generation_completed)
        self.worker.failed.connect(self.generation_failed)
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

    def generation_completed(self, output: str) -> None:
        self.output_path = Path(output)
        self.open_output_button.setEnabled(True)

    def generation_failed(self, message: str) -> None:
        self.status_label.setText(message)
        if not message.lower().startswith("generation cancelled"):
            QMessageBox.critical(self, "Generation stopped", message)

    def _worker_finished(self) -> None:
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.thread = None
        self.worker = None
        if self._close_when_finished:
            self.close()

    def open_output_folder(self) -> None:
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_path.parent)))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker:
            self.worker.cancel()
            self._close_when_finished = True
            self.status_label.setText("Cancelling safely before closing…")
            event.ignore()
            return
        event.accept()
