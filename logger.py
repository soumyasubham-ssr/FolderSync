"""Thread-safe log emitter for the in-app log panel, backed by a rotating log file."""
from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from config import LOG_PATH


def setup_file_logging(path: Path = LOG_PATH, level: str = "INFO") -> None:
    """Write a persistent log (1 MB x 3 files) next to the database."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    root = logging.getLogger("folder_sync")
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


class AppLogger(QObject):
    """Qt signals are queued across threads, so worker threads may call ``log`` directly."""

    entry = Signal(str, str, str, str, str)  # time, pair, operation, status, detail

    _LEVELS = {"Error": logging.ERROR, "Warning": logging.WARNING}

    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger("folder_sync")

    def log(self, pair: str, operation: str, status: str = "Success", detail: str = "") -> None:
        self._logger.log(self._LEVELS.get(status, logging.INFO), "[%s] %s: %s %s", pair, operation, status, detail)
        self.entry.emit(datetime.now().strftime("%H:%M:%S"), pair, operation, status, detail)
