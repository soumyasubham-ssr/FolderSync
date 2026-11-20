# Architecture

```
main.py ── QApplication, logging, wiring
│
├── ui/main_window.py    Pair table, log panel, tray icon
├── ui/dialogs.py        Add / edit pair dialog (validates input)
├── ui/settings_dialog.py  Preferences and the Windows "Run" registry key
│
├── sync_engine.py       SyncEngine: watchers, debounce, copy/delete/rename, full mirror
├── watcher.py           watchdog Observer → callback(side, kind, src, dest, is_dir)
├── models.py            FolderPair, SyncMode, PairStatus
├── database.py          SQLite repository (short-lived connections)
├── logger.py            AppLogger (Qt signal) + rotating file log
└── config.py            Version, paths, defaults
```

## Event flow

1. `FolderWatcher` runs one watchdog `Observer` per pair, with recursive watches on both folders. Every event is tagged with the side it came from.
2. `SyncEngine._event` drops the event when:
   - the pair is not being watched,
   - a full mirror is running for that pair, or
   - the path was written by the engine itself less than 1 second ago (echo suppression).
3. Events are **debounced** per path for 0.65 s, so a burst of writes becomes one copy.
4. The work runs on a 4-thread `ThreadPoolExecutor`. `FolderPair.source_for(side)` decides the direction, and returns `None` when the pair's mode ignores that side.
5. The operation is applied:
   - **created / modified**: `shutil.copy2`, skipped when the target already has the same size and mtime.
   - **moved**: `os.replace` on the target when possible, otherwise delete + copy. A move out of the watched folder counts as a delete.
   - **deleted**: remove the target. The target itself is inspected, because Windows reports deleted folders as files.
6. Status and log entries go back to the UI through Qt signals. These are queued across threads, so workers never touch widgets.

## Why there are no sync loops

Every write the engine makes produces an event on the other side. Two mechanisms stop that from bouncing back:

- The written path is put on a short ignore list before the write starts and again after it finishes.
- Even if an echo gets through, the file on both sides now has the same size and mtime (`copy2` keeps the mtime), so the copy is skipped.

## Locked files

Windows error codes 32 and 33 (sharing and lock violations) are retried 4 times with linear backoff. After that the file is skipped with a warning and picked up on its next change.

## Full mirror (`Start Pair`)

`_initial` walks the source with `rglob` and copies anything that differs. It uses a 2 s mtime tolerance for FAT/exFAT drives. It then walks the target deepest-first and deletes anything not in the source. Live events for that pair are ignored while the mirror runs.

## Threading rules

- `SyncEngine._lock` (an `RLock`) protects the watcher, timer, ignore and running-mirror maps.
- SQLite connections are opened per call, so worker threads never share a connection.
