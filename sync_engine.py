"""Event-driven synchronisation with debouncing, retry and feedback suppression."""
from __future__ import annotations

import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from models import FolderPair, PairStatus, SyncMode
from watcher import FolderWatcher

DEBOUNCE_SECONDS = 0.65     # coalesce bursts of events for the same path
SUPPRESS_SECONDS = 1.0      # skip echo events caused by our own writes (they are no-ops anyway)
COPY_RETRIES = 4
LOCKED_WINERRORS = (32, 33)  # sharing / lock violation
LIVE_MTIME_TOLERANCE = 0.01
FULL_MTIME_TOLERANCE = 2.0  # FAT/exFAT store modification times at 2 s resolution


def _is_locked(error: OSError) -> bool:
    return getattr(error, "winerror", None) in LOCKED_WINERRORS


def _key(path: os.PathLike | str) -> str:
    return os.path.normcase(os.fspath(path))


def _unchanged(source: Path, target: Path, tolerance: float) -> bool:
    """True when the target already holds the same file (size and mtime match)."""
    try:
        s, t = source.stat(), target.stat()
    except OSError:
        return False
    return s.st_size == t.st_size and abs(s.st_mtime - t.st_mtime) <= tolerance


class SyncEngine(QObject):
    status_changed = Signal(int, str)

    def __init__(self, db, logger, max_workers: int = 4) -> None:
        super().__init__()
        self.db, self.log = db, logger
        self._pairs: dict[int, FolderPair] = {}
        self._watchers: dict[int, FolderWatcher] = {}
        self._timers: dict[tuple[int, str], threading.Timer] = {}
        self._ignore: dict[str, float] = {}
        self._initial_running: set[int] = set()
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="FolderSync")

    # Pair lifecycle ---------------------------------------------------------
    def set_pairs(self, pairs: list[FolderPair]) -> None:
        with self._lock:
            self._pairs = {pair.id: pair for pair in pairs if pair.id is not None}

    @property
    def is_monitoring(self) -> bool:
        return bool(self._watchers)

    def is_watching(self, pair_id: int) -> bool:
        return pair_id in self._watchers

    def start_pair(self, pair_id: int) -> bool:
        with self._lock:
            pair = self._pairs.get(pair_id)
            if not pair or not pair.enabled or pair.paused or pair_id in self._watchers:
                return False
            if not (Path(pair.left_path).is_dir() and Path(pair.right_path).is_dir()):
                self._emit(pair_id, PairStatus.ERROR)
                self.log.log(pair.name, "Folder unavailable", "Error")
                return False
            watcher = FolderWatcher(
                pair.left_path, pair.right_path,
                lambda side, kind, src, dest, is_dir: self._event(pair_id, side, kind, src, dest, is_dir))
            watcher.start()
            self._watchers[pair_id] = watcher
        self._emit(pair_id, PairStatus.IDLE)
        self.log.log(pair.name, "Monitoring started")
        return True

    def stop_pair(self, pair_id: int) -> None:
        with self._lock:
            watcher = self._watchers.pop(pair_id, None)
            for key in [k for k in self._timers if k[0] == pair_id]:
                self._timers.pop(key).cancel()
            pair = self._pairs.get(pair_id)
        if watcher:
            watcher.stop()
        if pair:
            self._emit(pair_id, PairStatus.PAUSED)
            self.log.log(pair.name, "Monitoring paused")

    def start(self) -> None:
        """Start every enabled, unpaused pair."""
        for pair_id in list(self._pairs):
            self.start_pair(pair_id)

    def stop(self) -> None:
        for pair_id in list(self._watchers):
            self.stop_pair(pair_id)

    def refresh(self, pairs: list[FolderPair]) -> None:
        """Reload pair definitions and restart the watchers that were running."""
        active = set(self._watchers)
        self.stop()
        self.set_pairs(pairs)
        for pair_id in active:
            self.start_pair(pair_id)

    def shutdown(self) -> None:
        self.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)

    def run_now(self, pair_id: int, initial_side: str | None = None) -> None:
        pair = self._pairs.get(pair_id)
        if pair and pair_id not in self._initial_running:
            self._pool.submit(self._initial, pair, initial_side)

    # Live events ------------------------------------------------------------
    def _event(self, pair_id, side, kind, source, destination, is_dir) -> None:
        source_key = _key(source)
        now = time.monotonic()
        with self._lock:
            if pair_id not in self._watchers or pair_id in self._initial_running:
                return
            if self._ignore.get(source_key, 0) > now:
                return
            key = (pair_id, source_key)
            if previous := self._timers.pop(key, None):
                previous.cancel()
            timer = threading.Timer(DEBOUNCE_SECONDS, self._fire, (key, side, kind, source, destination, is_dir))
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _fire(self, key, side, kind, source, destination, is_dir) -> None:
        with self._lock:
            self._timers.pop(key, None)
        self._pool.submit(self._sync, key[0], side, kind, source, destination, is_dir)

    def _sync(self, pair_id, side, kind, source, destination, is_dir) -> None:
        pair = self._pairs.get(pair_id)
        roots = pair.source_for(side) if pair and pair.enabled and not pair.paused else None
        if not roots:
            return
        source_root, target_root = roots
        source = Path(source)
        try:
            old_target = target_root / source.relative_to(source_root)
            self._emit(pair_id, PairStatus.SYNCING)
            if kind == "deleted":
                self._remove(old_target, pair)
            elif kind == "moved" and destination:
                self._move(Path(destination), old_target, source_root, target_root, is_dir, pair)
            elif source.exists():
                self._copy(source, old_target, source.is_dir(), pair)
            pair.last_sync = self.db.mark_synced(pair_id)
            self._emit(pair_id, PairStatus.IDLE)
        except OSError as error:
            if _is_locked(error):
                self._emit(pair_id, PairStatus.IDLE)
                self.log.log(pair.name, "Skipped locked file", "Warning",
                             f"{source.name} is in use; it will sync on its next change.")
            else:
                self._fail(pair, "Sync failed", error)
        except Exception as error:  # never let a worker thread die silently
            self._fail(pair, "Sync failed", error)

    def _move(self, new_source, old_target, source_root, target_root, is_dir, pair) -> None:
        try:
            new_target = target_root / new_source.relative_to(source_root)
        except ValueError:  # moved out of the watched folder: treat as a delete
            self._remove(old_target, pair)
            return
        if old_target.exists() and not new_target.exists():
            # Rename in place instead of delete + full re-copy.
            self._suppress(old_target, new_target)
            new_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(old_target, new_target)
            self.log.log(pair.name, f"Renamed {old_target.name} → {new_target.name}")
        else:
            self._remove(old_target, pair)
            if new_source.exists():
                self._copy(new_source, new_target, is_dir, pair)

    # File operations --------------------------------------------------------
    def _copy(self, source: Path, target: Path, is_dir: bool, pair: FolderPair,
              tolerance: float = LIVE_MTIME_TOLERANCE) -> bool:
        """Copy one entry; returns ``False`` when the target is already up to date.

        Skipping identical files is also what stops copy echoes from looping
        between the two folders in bidirectional mode."""
        if is_dir:
            if target.is_dir():
                return False
            self._suppress(target)
            target.mkdir(parents=True, exist_ok=True)
            self.log.log(pair.name, f"Created folder {source.name}")
            return True
        if _unchanged(source, target, tolerance):
            return False
        self._suppress(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(COPY_RETRIES):
            try:
                shutil.copy2(source, target)
                break
            except OSError as error:
                if not _is_locked(error) or attempt == COPY_RETRIES - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))
        self._suppress(target)  # extend the window past the write itself
        self.log.log(pair.name, f"Copied {source.name}")
        return True

    def _remove(self, target: Path, pair: FolderPair) -> None:
        # Inspect the target itself: Windows reports deleted folders as files.
        if not os.path.lexists(target):
            return
        self._suppress(target)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
        self.log.log(pair.name, f"Deleted {target.name}")

    def _suppress(self, *paths: Path) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._ignore) > 1000:  # drop expired entries so the map stays small
                self._ignore = {k: v for k, v in self._ignore.items() if v > now}
            for path in paths:
                self._ignore[_key(path)] = now + SUPPRESS_SECONDS

    # Full mirror ------------------------------------------------------------
    def _initial(self, pair: FolderPair, initial_side: str | None = None) -> None:
        side = initial_side or ("right" if pair.mode is SyncMode.RIGHT_TO_LEFT else "left")
        roots = pair.source_for(side)
        if not roots:
            return
        source_root, target_root = roots
        with self._lock:
            self._initial_running.add(pair.id)
        self._emit(pair.id, PairStatus.SYNCING)
        try:
            copied = removed = 0
            for path in source_root.rglob("*"):
                copied += self._copy(path, target_root / path.relative_to(source_root), path.is_dir(), pair,
                                    FULL_MTIME_TOLERANCE)
            # Deepest paths first so folders are emptied before they are removed.
            for path in sorted(target_root.rglob("*"), reverse=True):
                if not os.path.lexists(source_root / path.relative_to(target_root)):
                    self._remove(path, pair)
                    removed += 1
            pair.last_sync = self.db.mark_synced(pair.id)
            self._emit(pair.id, PairStatus.IDLE)
            self.log.log(pair.name, "Full sync complete", "Success",
                         f"{copied} updated, {removed} removed")
        except Exception as error:
            self._fail(pair, "Full sync failed", error)
        finally:
            with self._lock:
                self._initial_running.discard(pair.id)

    # Helpers ----------------------------------------------------------------
    def _emit(self, pair_id: int, status: PairStatus) -> None:
        self.status_changed.emit(pair_id, status.value)

    def _fail(self, pair: FolderPair, operation: str, error: Exception) -> None:
        self._emit(pair.id, PairStatus.ERROR)
        self.log.log(pair.name, operation, "Error", str(error))
