"""Main window and system-tray user interface."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSplitter, QStyle, QSystemTrayIcon, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from config import APP_NAME, APP_VERSION, AUTHOR, HOMEPAGE, ICON_PATH
from models import FolderPair, PairStatus, SyncMode
from ui.dialogs import PairDialog
from ui.settings_dialog import SettingsDialog

MAX_LOG_ROWS = 2000  # keep the log panel responsive during long sessions
STATUS_COLUMN = 4
ACTIVE_COLOR, INACTIVE_COLOR = "#2f8f4e", "#a64646"


class MainWindow(QMainWindow):
    def __init__(self, db, log, engine):
        super().__init__()
        self.db, self.log, self.engine = db, log, engine
        self.pairs = []
        self.monitoring = False
        self._tray_hint_shown = False
        self.icon = QIcon(str(ICON_PATH))
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
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
        self.table.doubleClicked.connect(lambda _index: self.edit())

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
        icon = self.icon if not self.icon.isNull() else self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.activated.connect(self._tray_activated)
        menu = QMenu(self)
        for label, handler in (("Open", self._restore), ("Settings", self.settings),
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
            values = [pair.name, pair.left_path, pair.right_path, pair.mode.label, self._status_of(pair),
                      pair.last_sync or "Never", "Yes" if pair.enabled else "No"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        self._update_pair_controls()

    def _status_of(self, pair: FolderPair) -> str:
        if pair.status is PairStatus.IDLE and not self.engine.is_watching(pair.id):
            return "Stopped"
        return pair.status.value

    def selected(self) -> FolderPair | None:
        rows = self.table.selectionModel().selectedRows()
        return self.pairs[rows[0].row()] if rows else None

    def add(self):
        dialog = PairDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.db.save_pair(dialog.value())
            self.reload()

    def edit(self):
        if pair := self.selected():
            dialog = PairDialog(self, pair)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.db.save_pair(dialog.value())
                self.reload()
                self.engine.refresh(self.pairs)

    def remove(self):
        if pair := self.selected():
            if QMessageBox.question(self, "Remove folder pair", f"Remove '{pair.name}'?") == QMessageBox.StandardButton.Yes:
                self.engine.stop_pair(pair.id)
                self.db.delete_pair(pair.id)
                self.reload()

    def start_pair(self):
        if pair := self.selected():
            if not pair.enabled:
                QMessageBox.information(self, "Start pair", f"'{pair.name}' is disabled. Edit it and tick Enabled first.")
                return
            initial_side = None
            if pair.mode is SyncMode.BIDIRECTIONAL:
                choice = QMessageBox(self)
                choice.setWindowTitle("Initial synchronization")
                choice.setIcon(QMessageBox.Icon.Question)
                choice.setText("Choose the source for the existing files.")
                choice.setInformativeText(
                    "The selected folder will be mirrored to the other folder before live bidirectional "
                    "monitoring begins. Files in the target that do not exist in the source will be deleted.")
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
            if self.engine.start_pair(pair.id) or self.engine.is_watching(pair.id):
                self.engine.run_now(pair.id, initial_side)
            self._refresh_monitor_state()

    def stop_pair(self):
        if pair := self.selected():
            if not pair.paused:
                self.engine.stop_pair(pair.id)
                pair.paused = True
                self.db.save_pair(pair)
                self.reload()
            self._refresh_monitor_state()

    def _refresh_monitor_state(self) -> None:
        self.monitoring = self.engine.is_monitoring
        label = "Monitoring" if self.monitoring else "Stopped"
        self.monitor_indicator.setText(f"●  {label}")
        self.monitor_indicator.setStyleSheet(f"color: {ACTIVE_COLOR if self.monitoring else INACTIVE_COLOR};")

    def _update_pair_controls(self):
        pair = self.selected()
        for button in (self.edit_button, self.remove_button, self.start_pair_button):
            button.setEnabled(pair is not None)
        self.pair_pause_button.setEnabled(pair is not None and not pair.paused)

    def set_status(self, pair_id, status):
        for row, pair in enumerate(self.pairs):
            if pair.id == pair_id:
                if item := self.table.item(row, STATUS_COLUMN):
                    item.setText(status)
                    if pair.last_sync:
                        self.table.item(row, 5).setText(pair.last_sync)
                break

    def add_log(self, *values):
        if self.logs.rowCount() >= MAX_LOG_ROWS:
            self.logs.removeRow(0)
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
            self.reload()
            self._refresh_monitor_state()

    def about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h2>{APP_NAME}</h2><p><b>Version {APP_VERSION}</b></p>"
            f"<h3>Designed &amp; Developed by</h3><h2>{AUTHOR}</h2>"
            "<p>Building productivity software, automation tools, desktop applications, and AI-powered "
            "solutions with a focus on simplicity, performance, and reliability.</p>"
            "<p><b>Contact</b><br>Email: <a href='mailto:soumyasubham.ssr@gmail.com'>soumyasubham.ssr@gmail.com</a>"
            f"<br>GitHub: <a href='{HOMEPAGE}'>{HOMEPAGE.removeprefix('https://')}</a></p>"
            f"<p>© 2026 {AUTHOR}. Released under the MIT License.</p>",
        )

    def _restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._restore()

    def quit(self):
        self.engine.shutdown()
        self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.engine.shutdown()
            event.accept()
            QApplication.quit()
            return
        self.hide()
        event.ignore()
        if not self._tray_hint_shown:  # only nag once per session
            self._tray_hint_shown = True
            self._tray.showMessage(APP_NAME, "Still running in the system tray.")
