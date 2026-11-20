"""Thin watchdog adapter that reports which side of a pair changed."""
from __future__ import annotations

from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# callback(side, event_type, src_path, dest_path, is_directory)
EventCallback = Callable[[str, str, str, "str | None", bool], None]

_IGNORED_EVENTS = {"opened", "closed", "closed_no_write"}


class _Handler(FileSystemEventHandler):
    def __init__(self, side: str, callback: EventCallback) -> None:
        super().__init__()
        self.side, self.callback = side, callback

    def on_any_event(self, event: FileSystemEvent) -> None:
        # Directory "modified" events carry no useful synchronization operation.
        if event.event_type in _IGNORED_EVENTS or (event.is_directory and event.event_type == "modified"):
            return
        self.callback(self.side, event.event_type, event.src_path,
                      getattr(event, "dest_path", None) or None, event.is_directory)


class FolderWatcher:
    def __init__(self, left: str, right: str, callback: EventCallback) -> None:
        self._observer = Observer()
        self._observer.schedule(_Handler("left", callback), left, recursive=True)
        self._observer.schedule(_Handler("right", callback), right, recursive=True)

    def start(self) -> None:
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=3)
