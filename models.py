"""Domain models used by the UI, persistence, and synchronization layers."""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SyncMode(str, Enum):
    BIDIRECTIONAL = "bidirectional"
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"

    @property
    def label(self) -> str:
        return _MODE_LABELS[self]


_MODE_LABELS = {
    SyncMode.BIDIRECTIONAL: "Bidirectional",
    SyncMode.LEFT_TO_RIGHT: "Left → Right",
    SyncMode.RIGHT_TO_LEFT: "Right → Left",
}


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

    @property
    def status(self) -> PairStatus:
        if not self.enabled:
            return PairStatus.DISABLED
        return PairStatus.PAUSED if self.paused else PairStatus.IDLE

    def validate(self) -> str | None:
        """Return a user-facing error message, or ``None`` when the pair is usable."""
        if not (self.name.strip() and self.left_path.strip() and self.right_path.strip()):
            return "A name and both folders are required."
        left = os.path.normcase(os.path.abspath(self.left_path))
        right = os.path.normcase(os.path.abspath(self.right_path))
        if left == right:
            return "The left and right folders must be different."
        if left.startswith(right.rstrip(os.sep) + os.sep) or right.startswith(left.rstrip(os.sep) + os.sep):
            return "One folder cannot be inside the other; that would sync endlessly."
        return None

    def source_for(self, event_side: str) -> tuple[Path, Path] | None:
        """Return ``(source_root, target_root)`` for a change on ``event_side``,
        or ``None`` when this pair's direction ignores that side."""
        if self.mode is SyncMode.LEFT_TO_RIGHT and event_side != "left":
            return None
        if self.mode is SyncMode.RIGHT_TO_LEFT and event_side != "right":
            return None
        left, right = Path(self.left_path), Path(self.right_path)
        return (left, right) if event_side == "left" else (right, left)
