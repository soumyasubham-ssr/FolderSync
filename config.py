"""Application paths and default settings."""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Folder Sync"
# File layout deliberately keeps runtime state outside the install directory.
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FolderSync"
DATABASE_PATH = DATA_DIR / "folder_sync.db"

DEFAULT_SETTINGS: dict[str, str] = {
    "theme": "system",
    "logging_level": "INFO",
    "auto_start_sync": "0",
    "start_with_windows": "0",
    "run_in_background": "1",
    "run_in_tray": "1",
    "minimize_to_tray": "1",
    "default_sync_mode": "bidirectional",
    "conflict_behavior": "ask",
    "window_geometry": "",
}
