"""Add / edit dialog for a folder pair."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from models import FolderPair, SyncMode


class PairDialog(QDialog):
    def __init__(self, parent=None, pair: FolderPair | None = None) -> None:
        super().__init__(parent)
        self._pair = pair
        self.setWindowTitle("Edit Folder Pair" if pair else "Add Folder Pair")
        self.setMinimumWidth(560)

        self.name = QLineEdit(pair.name if pair else "")
        self.left = QLineEdit(pair.left_path if pair else "")
        self.right = QLineEdit(pair.right_path if pair else "")
        self.mode = QComboBox()
        for mode in SyncMode:
            self.mode.addItem(mode.label, mode.value)
        if pair:
            self.mode.setCurrentIndex(self.mode.findData(pair.mode.value))
        self.enabled = QCheckBox("Enabled")
        self.enabled.setChecked(pair.enabled if pair else True)

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Left folder", self._browse_row(self.left))
        form.addRow("Right folder", self._browse_row(self.right))
        form.addRow("Mode", self.mode)
        form.addRow("", self.enabled)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_row(self, edit: QLineEdit) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: self._pick(edit))
        layout.addWidget(edit)
        layout.addWidget(button)
        return row

    def _pick(self, edit: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder", edit.text() or str(Path.home()))
        if folder:
            edit.setText(folder)

    def accept(self) -> None:
        if error := self.value().validate():
            QMessageBox.warning(self, "Folder pair", error)
            return
        super().accept()

    def value(self) -> FolderPair:
        """The edited pair; runtime state (paused, last sync) is carried over."""
        old = self._pair
        return FolderPair(
            id=old.id if old else None,
            name=self.name.text().strip(),
            left_path=self.left.text().strip(),
            right_path=self.right.text().strip(),
            mode=SyncMode(self.mode.currentData()),
            enabled=self.enabled.isChecked(),
            paused=old.paused if old else False,
            last_sync=old.last_sync if old else None,
        )
