"""Domain models used by the UI, persistence, and synchronization layers."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SyncMode(str, Enum):
    BIDIRECTIONAL = "bidirectional"
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"

    @property
    def label(self) -> str:
        return {
            self.BIDIRECTIONAL: "Bidirectional",
            self.LEFT_TO_RIGHT: "Left → Right",
            self.RIGHT_TO_LEFT: "Right → Left",
        }[self]


class PairStatus(str, Enum):
    IDLE = "Idle"
    SYNCING = "Syncing"
    ERROR = "Error"
    PAUSED = "Paused"
    DISABLED = "Disabled"


@dataclass(slots=True)
class FolderPair:
    id: int | None
    name: str
    left_path: str
    right_path: str
    mode: SyncMode = SyncMode.BIDIRECTIONAL
    enabled: bool = True
    paused: bool = False
    last_sync: str | None = None

    def source_for(self, changed_path: Path, event_side: str) -> tuple[Path, Path] | None:
        """Return source and target roots, honoring this pair's direction."""
        if self.mode is SyncMode.LEFT_TO_RIGHT and event_side != "left":
            return None
        if self.mode is SyncMode.RIGHT_TO_LEFT and event_side != "right":
            return None
        return (Path(self.left_path), Path(self.right_path)) if event_side == "left" else (Path(self.right_path), Path(self.left_path))
