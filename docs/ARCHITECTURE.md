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
   - it is an *echo* of the engine's own write (see below).
3. Events are **debounced** per path for 0.65 s, so a burst of writes becomes one copy.
4. The work runs on a 4-thread `ThreadPoolExecutor`. `FolderPair.source_for(side)` decides the direction, and returns `None` when the pair's mode ignores that side.
5. The operation is applied:
   - **created / modified**: `shutil.copy2`, skipped when the target already has the same size and mtime.
   - **moved**: `os.replace` on the target when possible, otherwise delete + copy. A move out of the watched folder counts as a delete.
   - **deleted**: remove the target. The target itself is inspected, because Windows reports deleted folders as files.
6. Status and log entries go back to the UI through Qt signals. These are queued across threads, so workers never touch widgets.

## Why there are no sync loops

Every write the engine makes produces events on the other side, and on Windows they arrive about a second later. Two mechanisms stop them from bouncing back:

- **Echo signatures.** Before a write, the target path is marked *pending*, and every event on it is ignored. Afterwards the engine records what the write left on disk: absent, a folder, or `(size, mtime_ns)`. For 5 seconds, an event on that path is treated as an echo only while the path still matches that record. If the user changes the file in the meantime, the record no longer matches, so the change is synced and never swallowed.
- **Identical-file check.** Even if an echo gets through, both sides now have the same size and mtime (`copy2` keeps the mtime), so the copy is skipped.

## Locked files

Windows error codes 32 and 33 (sharing and lock violations) are retried 4 times with linear backoff. After that the file is skipped with a warning and picked up on its next change.

## Full mirror (`Start Pair`)

`_initial` walks the source with `rglob` and copies anything that differs. It uses a 2 s mtime tolerance for FAT/exFAT drives. It then walks the target deepest-first and deletes anything not in the source. Live events for that pair are ignored while the mirror runs.

## Threading rules

- `SyncEngine._lock` (an `RLock`) protects the watcher, timer, ignore and running-mirror maps.
- SQLite connections are opened per call, so worker threads never share a connection.
