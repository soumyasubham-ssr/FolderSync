"""Main window and system-tray user interface."""
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSplitter, QStyle, QSystemTrayIcon, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ui.dialogs import PairDialog
from ui.settings_dialog import SettingsDialog
from models import SyncMode


class MainWindow(QMainWindow):
    def __init__(self, db, log, engine):
        super().__init__()
        self.db, self.log, self.engine = db, log, engine
        self.pairs = []
        self.monitoring = False
        base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        self.icon = QIcon(str(base_path / "icon.ico"))
        self.setWindowTitle("Folder Sync")
        self.setWindowIcon(self.icon)
        self.resize(1180, 720)
        self._build()
        self._create_tray()
        log.entry.connect(self.add_log)
        engine.status_changed.connect(self.set_status)
        self.reload()
        QTimer.singleShot(0, self._apply_startup_preferences)

    def _build(self):
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 18)

        heading = QHBoxLayout()
        heading.addWidget(QLabel("<h2>Folder Pairs</h2>"))
        heading.addStretch()
        self.add_button = QPushButton("Add Folder Pair")
        self.edit_button = QPushButton("Edit")
        self.pair_pause_button = QPushButton("Stop Pair")
        self.remove_button = QPushButton("Remove")
        self.start_pair_button = QPushButton("Start Pair")
        self.refresh_button = QPushButton("Refresh")
        self.settings_button = QPushButton("Settings")
        self.about_button = QPushButton("About")
        for button, slot in ((self.start_pair_button, self.start_pair), (self.pair_pause_button, self.stop_pair),
                             (self.refresh_button, self.reload), (self.add_button, self.add),
                             (self.edit_button, self.edit), (self.remove_button, self.remove),
                             (self.settings_button, self.settings),
                             (self.about_button, self.about)):
            button.clicked.connect(slot)
            heading.addWidget(button)
        layout.addLayout(heading)
        self.monitor_indicator = QLabel("●  Stopped")
        self.monitor_indicator.setObjectName("monitorStatus")
        heading.addWidget(self.monitor_indicator)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Name", "Left Folder", "Right Folder", "Mode", "Status", "Last Sync", "Enabled"])
        self._configure_table(self.table, [1, 2])
        splitter.addWidget(self.table)
        self.logs = QTableWidget(0, 5)
        self.logs.setHorizontalHeaderLabels(["Time", "Folder Pair", "Operation", "Status", "Detail"])
        self._configure_table(self.logs, [2, 4])
        splitter.addWidget(self.logs)
        splitter.setSizes([410, 245])
        self.table.itemSelectionChanged.connect(self._update_pair_controls)

        self.setStyleSheet("QLabel#monitorStatus { font-weight: 600; color: #a64646; padding: 4px 10px; }")

    @staticmethod
    def _configure_table(table, stretch_columns):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in stretch_columns:
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)

    def _create_tray(self):
        self._tray = QSystemTrayIcon(self.icon or self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
        menu = QMenu(self)
        for label, handler in (("Open", self.showNormal), ("Settings", self.settings),
                               ("About", self.about), ("Exit", self.quit)):
            action = QAction(label, self)
            action.triggered.connect(handler)
            menu.addAction(action)
        self._tray.setContextMenu(menu)
        self._tray.show()

    def reload(self):
        self.pairs = self.db.list_pairs()
        self.engine.set_pairs(self.pairs)
        self.table.setRowCount(0)
        for pair in self.pairs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            status = "Disabled" if not pair.enabled else "Paused" if pair.paused else "Idle"
            values = [pair.name, pair.left_path, pair.right_path, pair.mode.label, status, pair.last_sync or "Never", "Yes" if pair.enabled else "No"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        self._update_pair_controls()

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.pairs[rows[0].row()] if rows else None

    def add(self):
        dialog = PairDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pair = dialog.value()
            if not (pair.name.strip() and pair.left_path.strip() and pair.right_path.strip()):
                QMessageBox.warning(self, "Folder Sync", "A name and both folders are required.")
                return
            self.db.save_pair(pair)
            self.reload()

    def edit(self):
        if pair := self.selected():
            dialog = PairDialog(self, pair)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.db.save_pair(dialog.value(pair.id))
                self.reload()

    def remove(self):
        if pair := self.selected():
            if QMessageBox.question(self, "Remove folder pair", f"Remove '{pair.name}'?") == QMessageBox.StandardButton.Yes:
                self.db.delete_pair(pair.id)
                self.reload()

    def toggle(self):
        if pair := self.selected():
            pair.paused = not pair.paused
            self.db.save_pair(pair)
            self.reload()
            self.engine.refresh(self.pairs)

    def start_pair(self):
        if pair := self.selected():
            initial_side = None
            if pair.mode is SyncMode.BIDIRECTIONAL:
                choice = QMessageBox(self)
                choice.setWindowTitle("Initial synchronization")
                choice.setIcon(QMessageBox.Icon.Question)
                choice.setText("Choose the source for the existing files.")
                choice.setInformativeText("The selected folder will be mirrored to the other folder before live bidirectional monitoring begins. Files in the target that do not exist in the source will be deleted.")
                left_button = choice.addButton("Left → Right", QMessageBox.ButtonRole.AcceptRole)
                right_button = choice.addButton("Right → Left", QMessageBox.ButtonRole.ActionRole)
                choice.addButton(QMessageBox.StandardButton.Cancel)
                choice.exec()
                if choice.clickedButton() == left_button:
                    initial_side = "left"
                elif choice.clickedButton() == right_button:
                    initial_side = "right"
                else:
                    return
            if pair.paused:
                pair.paused = False
                self.db.save_pair(pair)
                self.reload()
            self.engine.start_pair(pair.id)
            self.engine.run_now(pair.id, initial_side)
            self.monitoring = True
            self._update_monitor_indicator("Pair monitoring active")

    def stop_pair(self):
        if pair := self.selected():
            if not pair.paused:
                self.engine.stop_pair(pair.id)
                pair.paused = True
                self.db.save_pair(pair)
                self.reload()
            self.monitoring = self.engine.is_monitoring
            self._update_monitor_indicator("Pair monitoring active" if self.monitoring else "Stopped")

    def run(self):
        if pair := self.selected():
            self.engine.run_now(pair.id)

    def start(self):
        self.reload()
        self.engine.start()
        self.monitoring = True
        self._update_monitor_indicator()

    def pause(self):
        self.engine.stop()
        self.monitoring = False
        self._update_monitor_indicator("Paused")

    def toggle_monitor(self):
        if self.monitoring:
            self.pause()
        else:
            self.start()

    def stop(self):
        self.engine.stop()
        self.monitoring = False
        self._update_monitor_indicator("Stopped")

    def _update_monitor_indicator(self, label=None):
        label = label or ("Monitoring" if self.monitoring else "Stopped")
        active = label in ("Monitoring", "Pair monitoring active")
        self.monitor_indicator.setText(f"{'●' if active else '●'}  {label}")
        self.monitor_indicator.setStyleSheet(f"color: {'#2f8f4e' if active else '#a64646'};")

    def _update_pair_controls(self):
        pair = self.selected()
        self.start_pair_button.setEnabled(pair is not None)
        self.pair_pause_button.setEnabled(pair is not None and not pair.paused)
        self.pair_pause_button.setText("Stop Pair")

    def set_status(self, pair_id, status):
        for row, pair in enumerate(self.pairs):
            if pair.id == pair_id:
                self.table.item(row, 4).setText(status)
                break

    def add_log(self, *values):
        row = self.logs.rowCount()
        self.logs.insertRow(row)
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            self.logs.setItem(row, column, item)
        self.logs.scrollToBottom()

    def settings(self):
        SettingsDialog(self.db, self).exec()

    def _apply_startup_preferences(self):
        if self.db.settings().get("auto_start_sync") == "1":
            self.engine.start()
            self.monitoring = self.engine.is_monitoring
            self._update_monitor_indicator("Pair monitoring active" if self.monitoring else "Stopped")

    def about(self):
        QMessageBox.about(self, "About Folder Sync", "<h2>Folder Sync</h2><p><b>Version 1.0.0</b></p><h3>Designed &amp; Developed by</h3><h2>Soumya Subham Rout</h2><p>Building productivity software, automation tools, desktop applications, and AI-powered solutions with a focus on simplicity, performance, and reliability.</p><p><b>Contact</b><br>Email: <a href='mailto:soumyasubham.ssr@gmail.com'>soumyasubham.ssr@gmail.com</a><br>GitHub: <a href='https://github.com/soumyasubham-ssr'>github.com/soumyasubham-ssr</a></p><p>© 2026 Soumya Subham Rout. All Rights Reserved.</p>")

    def quit(self):
        self.engine.stop()
        QApplication.quit()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
        self._tray.showMessage("Folder Sync", "Still running in the system tray.")
