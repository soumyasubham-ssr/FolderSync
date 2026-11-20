"""Application metadata, paths and default settings."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Folder Sync"
APP_VERSION = "1.1.0"
APP_ID = "com.soumya.foldersync"
AUTHOR = "Soumya Subham Rout"
HOMEPAGE = "https://github.com/soumyasubham-ssr/FolderSync"

# Runtime state lives outside the install directory so upgrades never touch it.
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FolderSync"
DATABASE_PATH = DATA_DIR / "folder_sync.db"
LOG_PATH = DATA_DIR / "folder_sync.log"

# Bundled resources resolve from the PyInstaller temp dir when frozen.
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ICON_PATH = RESOURCE_DIR / "icon.ico"

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
