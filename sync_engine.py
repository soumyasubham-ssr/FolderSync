"""Event-driven synchronisation with debouncing, retry and feedback suppression."""
from __future__ import annotations

import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from watcher import FolderWatcher


class SyncEngine(QObject):
    status_changed = Signal(int, str)

    def __init__(self, db, logger):
        super().__init__()
        self.db, self.log = db, logger
        self._pairs, self._watchers, self._timers = {}, {}, {}
        self._ignore = {}
        self._initial_running = {}
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="FolderSync")

    def set_pairs(self, pairs):
        with self._lock:
            self._pairs = {pair.id: pair for pair in pairs if pair.id is not None}

    @property
    def is_monitoring(self):
        return bool(self._watchers)

    def start_pair(self, pair_id):
        pair = self._pairs.get(pair_id)
        if not pair or not pair.enabled or pair.paused or pair_id in self._watchers:
            return
        left, right = Path(pair.left_path), Path(pair.right_path)
        if not left.is_dir() or not right.is_dir():
            self.status_changed.emit(pair_id, "Error")
            self.log.log(pair.name, "Folder unavailable", "Error")
            return
        watcher = FolderWatcher(pair.left_path, pair.right_path,
                                lambda side, kind, source, destination, is_dir: self._event(pair_id, side, kind, source, destination, is_dir))
        watcher.start()
        self._watchers[pair_id] = watcher
        self.status_changed.emit(pair_id, "Idle")
        self.log.log(pair.name, "Monitoring started")

    def stop_pair(self, pair_id):
        watcher = self._watchers.pop(pair_id, None)
        if watcher:
            watcher.stop()
        for key, timer in list(self._timers.items()):
            if key[0] == pair_id:
                timer.cancel()
                self._timers.pop(key, None)
        if pair := self._pairs.get(pair_id):
            self.status_changed.emit(pair_id, "Paused")
            self.log.log(pair.name, "Monitoring paused")

    def start(self):
        """Compatibility method: starts every enabled unpaused pair."""
        for pair_id in list(self._pairs):
            self.start_pair(pair_id)

    def stop(self):
        for pair_id in list(self._watchers):
            self.stop_pair(pair_id)

    def refresh(self, pairs):
        active = set(self._watchers)
        self.stop()
        self.set_pairs(pairs)
        for pair_id in active:
            self.start_pair(pair_id)

    def run_now(self, pair_id, initial_side=None):
        if pair := self._pairs.get(pair_id):
            self._pool.submit(self._initial, pair, initial_side)

    def _event(self, pair_id, side, kind, source, destination, is_dir):
        source_key = os.path.normcase(source)
        with self._lock:
            if pair_id not in self._watchers or self._ignore.get(source_key, 0) > time.monotonic():
                return
            if self._initial_running.get(pair_id):
                return
            key = (pair_id, source_key)
            if previous := self._timers.pop(key, None):
                previous.cancel()
            timer = threading.Timer(0.65, lambda: self._pool.submit(self._sync, pair_id, side, kind, source, destination, is_dir))
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _sync(self, pair_id, side, kind, source, destination, is_dir):
        pair = self._pairs.get(pair_id)
        roots = pair.source_for(Path(source), side) if pair and pair.enabled and not pair.paused else None
        if not roots:
            return
        source_root, target_root = roots
        try:
            old_target = target_root / Path(source).relative_to(source_root)
            self.status_changed.emit(pair_id, "Syncing")
            if kind == "deleted":
                self._remove(old_target, is_dir, pair)
            elif kind == "moved" and destination:
                new_source = Path(destination)
                self._remove(old_target, is_dir, pair)
                try:
                    new_target = target_root / new_source.relative_to(source_root)
                except ValueError:
                    pass
                else:
                    if new_source.exists():
                        self._copy(new_source, new_target, is_dir, pair)
            elif Path(source).exists():
                self._copy(Path(source), old_target, is_dir, pair)
            pair.last_sync = self.db.mark_synced(pair_id)
            self.status_changed.emit(pair_id, "Idle")
        except OSError as error:
            if getattr(error, "winerror", None) in (32, 33):
                self.status_changed.emit(pair_id, "Idle")
                self.log.log(pair.name, "Skipped locked file", "Warning", f"{Path(source).name} is in use; it will sync on its next change.")
            else:
                self.status_changed.emit(pair_id, "Error")
                self.log.log(pair.name, "Sync failed", "Error", str(error))
        except Exception as error:
            self.status_changed.emit(pair_id, "Error")
            self.log.log(pair.name, "Sync failed", "Error", str(error))

    def _copy(self, source, target, is_dir, pair):
        target.parent.mkdir(parents=True, exist_ok=True)
        if is_dir:
            target.mkdir(parents=True, exist_ok=True)
            operation = f"Created folder {source.name}"
        else:
            for attempt in range(4):
                try:
                    shutil.copy2(source, target)
                    break
                except OSError as error:
                    if getattr(error, "winerror", None) not in (32, 33) or attempt == 3:
                        raise
                    time.sleep(0.5 * (attempt + 1))
            operation = f"Copied {source.name}"
        self._suppress(target)
        self.log.log(pair.name, operation)

    def _remove(self, target, is_dir, pair):
        if not target.exists():
            return
        if is_dir:
            shutil.rmtree(target)
        else:
            target.unlink()
        self._suppress(target)
        self.log.log(pair.name, f"Deleted {target.name}")

    def _suppress(self, path):
        self._ignore[os.path.normcase(str(path))] = time.monotonic() + 3

    def _initial(self, pair, initial_side=None):
        side = initial_side or ("right" if pair.mode.value == "right_to_left" else "left")
        roots = pair.source_for(Path(pair.right_path if side == "right" else pair.left_path), side)
        if not roots:
            return
        source_root, target_root = roots
        self._initial_running[pair.id] = True
        self.status_changed.emit(pair.id, "Syncing")
        try:
            for path in source_root.rglob("*"):
                self._copy(path, target_root / path.relative_to(source_root), path.is_dir(), pair)
            for path in sorted(target_root.rglob("*"), reverse=True):
                corresponding = source_root / path.relative_to(target_root)
                if not corresponding.exists():
                    self._remove(path, path.is_dir(), pair)
            pair.last_sync = self.db.mark_synced(pair.id)
            self.status_changed.emit(pair.id, "Idle")
        except Exception as error:
            self.status_changed.emit(pair.id, "Error")
            self.log.log(pair.name, "Run now failed", "Error", str(error))
        finally:
            self._initial_running.pop(pair.id, None)
