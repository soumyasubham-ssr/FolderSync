# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-11-20

### Added
- Renames are mirrored as renames (`os.replace`) instead of delete + re-copy.
- The full mirror skips files that are already identical, and logs a summary ("N updated, M removed").
- Input validation in the add/edit dialog: required fields, different folders, no nested folders.
- Rotating log file at `%LOCALAPPDATA%\FolderSync\folder_sync.log`.
- Clicking the tray icon restores the window. Double-clicking a pair opens it for editing.
- *Stopped* status for enabled pairs that are not being watched.
- Automated tests (`pytest`), a CI workflow (Windows + Linux), and a release workflow that builds `FolderSync.exe` with PyInstaller.
- `requirements.txt` (it was referenced by `launch.bat` but missing), `build.bat`, and documentation with screenshots.

### Fixed
- Editing a pair kept stale paths in a running watcher. The pair now restarts with the new settings.
- Editing a pair reset its *Paused* state and *Last Sync* time.
- Removing a running pair left its watcher running.
- Deleted folders were removed with `unlink()` because Windows reports them as files.
- Genuine edits made within 3 s of a sync were silently ignored. Echo detection now compares each path with what Folder Sync wrote to it, so only its own echoes are skipped.
- The echo-suppression map grew without limit.
- *Start Pair* on a disabled pair did nothing and gave no feedback.
- The About box showed version 1.0.0.
- The app crashed at startup on non-Windows platforms (`ctypes.windll`).
- *Exit* left worker threads running. The engine now shuts down cleanly.
- The tray notification no longer appears every time the window is closed.

### Changed
- All modules reformatted and typed. Dead code was removed (unused toggle, run and pause handlers).
- Version, author and paths are defined once in `config.py`.
- The log panel is capped at 2,000 rows so long sessions stay responsive.

## [1.0.1] - 2026-07-23

### Changed
- Updates after the initial release.

## [1.0.0] - 2026-07-23

### Added
- Initial release: folder pairs, bidirectional and one-way live sync, system tray, start with Windows.

[1.1.0]: https://github.com/soumyasubham-ssr/FolderSync/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/soumyasubham-ssr/FolderSync/releases/tag/v1.0.1
