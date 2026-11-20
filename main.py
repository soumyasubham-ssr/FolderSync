"""Folder Sync entry point."""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config import APP_ID, APP_NAME, APP_VERSION, ICON_PATH
from database import Database
from logger import AppLogger, setup_file_logging
from sync_engine import SyncEngine
from ui.main_window import MainWindow


def main() -> int:
    if sys.platform == "win32":
        # Gives the taskbar entry our own icon instead of python.exe's.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setQuitOnLastWindowClosed(False)  # the tray keeps the app alive

    db = Database()
    db.initialize()
    setup_file_logging(level=db.settings().get("logging_level", "INFO"))
    log = AppLogger()
    window = MainWindow(db, log, SyncEngine(db, log))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
