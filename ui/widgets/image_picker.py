from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget


class ImagePicker(QWidget):
    image_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path: Path | None = None
        self.preview = QLabel("No reference image — text-to-video mode")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(120)
        self.preview.setStyleSheet("border: 1px dashed #657; border-radius: 8px; color: #aaa;")
        choose = QPushButton("Choose image…")
        self.remove_button = QPushButton("Remove image")
        self.remove_button.setEnabled(False)
        choose.clicked.connect(self.choose_image)
        self.remove_button.clicked.connect(self.remove_image)
        buttons = QHBoxLayout()
        buttons.addWidget(choose)
        buttons.addWidget(self.remove_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.preview)
        layout.addLayout(buttons)

    def choose_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Choose reference image", "", "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not filename:
            return
        path = Path(filename)
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid image", f"The selected image could not be read.\n\n{exc}")
            return
        self.path = path
        pixmap = QPixmap(str(path)).scaled(
            420, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pixmap)
        self.preview.setToolTip(str(path))
        self.remove_button.setEnabled(True)
        self.image_changed.emit(path)

    def remove_image(self) -> None:
        self.path = None
        self.preview.setPixmap(QPixmap())
        self.preview.setText("No reference image — text-to-video mode")
        self.preview.setToolTip("")
        self.remove_button.setEnabled(False)
        self.image_changed.emit(None)
