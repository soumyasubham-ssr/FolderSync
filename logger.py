"""Thread-safe structured log emitter for the user-visible log panel."""
from __future__ import annotations
import logging
from datetime import datetime
from PySide6.QtCore import QObject, Signal

class AppLogger(QObject):
    entry = Signal(str, str, str, str, str)
    def __init__(self):
        super().__init__(); self._logger = logging.getLogger('folder_sync')
    def log(self, pair, operation, status='Success', detail=''):
        self._logger.info('[%s] %s: %s (%s)', pair, operation, status, detail)
        self.entry.emit(datetime.now().strftime('%H:%M:%S'), pair, operation, status, detail)
