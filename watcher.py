"""Small watchdog adapter that retains the exact Windows event type."""
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class _Handler(FileSystemEventHandler):
    def __init__(self, side, callback):
        super().__init__()
        self.side, self.callback = side, callback

    def on_any_event(self, event):
        # Directory modified events contain no useful synchronization operation.
        if event.event_type == "opened" or (event.is_directory and event.event_type == "modified"):
            return
        self.callback(self.side, event.event_type, event.src_path, getattr(event, "dest_path", None), event.is_directory)


class FolderWatcher:
    def __init__(self, left, right, callback):
        self._observer = Observer()
        self._observer.schedule(_Handler("left", callback), left, recursive=True)
        self._observer.schedule(_Handler("right", callback), right, recursive=True)

    def start(self):
        self._observer.start()

    def stop(self):
        self._observer.stop()
        self._observer.join(timeout=3)
