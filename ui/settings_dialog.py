"""Application preference editor and Windows startup registration."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "FolderSync"


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.settings = db.settings()
        self.setWindowTitle("Folder Sync Settings")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.auto_start = QCheckBox("Start enabled folder pairs automatically when Folder Sync opens")
        self.auto_start.setChecked(self.settings.get("auto_start_sync") == "1")
        self.windows_start = QCheckBox("Start Folder Sync when you sign in to Windows")
        self.windows_start.setChecked(self.settings.get("start_with_windows") == "1")
        form.addRow("Auto-start sync", self.auto_start)
        form.addRow("Start with Windows", self.windows_start)
        layout.addLayout(form)
        layout.addWidget(QLabel("Only enabled, unpaused folder pairs are started automatically."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        self.db.set_setting("auto_start_sync", "1" if self.auto_start.isChecked() else "0")
        self.db.set_setting("start_with_windows", "1" if self.windows_start.isChecked() else "0")
        try:
            self._update_windows_startup(self.windows_start.isChecked())
        except OSError as error:
            self.db.set_setting("start_with_windows", "0")
            self.windows_start.setChecked(False)
            self.setWindowTitle(f"Folder Sync Settings — startup could not be updated: {error}")
            return
        self.accept()

    @staticmethod
    def _update_windows_startup(enabled: bool):
        """Register under the current user only; no administrator rights required."""
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                if getattr(sys, "frozen", False):
                    command = f'"{sys.executable}"'
                else:
                    main_file = Path(__file__).resolve().parents[1] / "main.py"
                    command = f'"{sys.executable}" "{main_file}"'
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
