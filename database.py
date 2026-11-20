"""SQLite repository. Connections are short-lived so every thread can use it safely."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from config import DATABASE_PATH, DEFAULT_SETTINGS
from models import FolderPair, SyncMode

_SCHEMA = """
CREATE TABLE IF NOT EXISTS folder_pairs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    left_path  TEXT    NOT NULL,
    right_path TEXT    NOT NULL,
    mode       TEXT    NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1,
    paused     INTEGER NOT NULL DEFAULT 0,
    last_sync  TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_PAIR_COLUMNS = "name, left_path, right_path, mode, enabled, paused, last_sync"


class Database:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = Path(path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def initialize(self) -> None:
        with self.connection() as con:
            con.executescript(_SCHEMA)
            con.executemany(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                DEFAULT_SETTINGS.items(),
            )

    # Folder pairs -----------------------------------------------------------
    def list_pairs(self) -> list[FolderPair]:
        with self.connection() as con:
            rows = con.execute("SELECT * FROM folder_pairs ORDER BY id").fetchall()
        return [self._pair(row) for row in rows]

    def save_pair(self, pair: FolderPair) -> FolderPair:
        values = (pair.name, pair.left_path, pair.right_path, pair.mode.value,
                  int(pair.enabled), int(pair.paused), pair.last_sync)
        with self.connection() as con:
            if pair.id is None:
                cursor = con.execute(
                    f"INSERT INTO folder_pairs({_PAIR_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)", values)
                pair.id = cursor.lastrowid
            else:
                con.execute(
                    "UPDATE folder_pairs SET name=?, left_path=?, right_path=?, mode=?, "
                    "enabled=?, paused=?, last_sync=? WHERE id=?", (*values, pair.id))
        return pair

    def delete_pair(self, pair_id: int) -> None:
        with self.connection() as con:
            con.execute("DELETE FROM folder_pairs WHERE id=?", (pair_id,))

    def mark_synced(self, pair_id: int) -> str:
        value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as con:
            con.execute("UPDATE folder_pairs SET last_sync=? WHERE id=?", (value, pair_id))
        return value

    # Settings ---------------------------------------------------------------
    def settings(self) -> dict[str, str]:
        with self.connection() as con:
            return {row["key"]: row["value"] for row in con.execute("SELECT key, value FROM settings")}

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as con:
            con.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    @staticmethod
    def _pair(row: sqlite3.Row) -> FolderPair:
        return FolderPair(
            id=row["id"], name=row["name"], left_path=row["left_path"], right_path=row["right_path"],
            mode=SyncMode(row["mode"]), enabled=bool(row["enabled"]), paused=bool(row["paused"]),
            last_sync=row["last_sync"],
        )
