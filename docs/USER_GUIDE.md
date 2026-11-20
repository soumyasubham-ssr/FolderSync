# Folder Sync User Guide

## Concepts

A **folder pair** links a *left* folder and a *right* folder. Each pair has its own **mode**:

| Mode | What it does |
|---|---|
| **Bidirectional** | Changes on either side are copied to the other side. |
| **Left → Right** | Changes on the left side are copied to the right side. Changes made on the right are ignored. |
| **Right → Left** | Changes on the right side are copied to the left side. Changes made on the left are ignored. |

> **Warning: Deletes are synchronized too.** Deleting a file in the source deletes it in the target. Folder Sync is a mirror, not a backup with history.

## Managing pairs

| Action | How |
|---|---|
| Add | **Add Folder Pair**, then fill in the name, both folders and the mode. |
| Edit | Select a row and click **Edit**, or double-click the row. A running pair restarts with the new settings. |
| Remove | Select a row and click **Remove**. This stops monitoring. Your files are not touched. |
| Enable / disable | Use the **Enabled** checkbox in the edit dialog. Disabled pairs never start. |

Folder Sync refuses a pair whose two folders are the same, or where one folder is inside the other, because that would sync endlessly.

## Starting and stopping

- **Start Pair** first runs a full mirror, then watches both folders live.
  - For a **bidirectional** pair you are asked which side is the source for that first mirror. The other side becomes an exact copy: files there that do not exist in the source **are deleted**.
  - For one-way pairs the source side is used automatically.
  - Files that already match (same size and modified time) are skipped, so restarting a big pair is fast.
- **Stop Pair** stops watching that pair and marks it *Paused*. Paused pairs are not started automatically.
- The indicator in the top-right shows **● Monitoring** while at least one pair is being watched.

### Status column

| Status | Meaning |
|---|---|
| Stopped | Enabled, but not being watched right now. |
| Idle | Being watched, with nothing to do. |
| Syncing | Copying or deleting files. |
| Paused | Stopped with **Stop Pair**. |
| Disabled | The **Enabled** checkbox is cleared. |
| Error | A folder is missing or an operation failed. Check the log panel. |

## Settings

| Setting | Effect |
|---|---|
| Auto-start sync | When Folder Sync opens, it starts every enabled, unpaused pair. |
| Start with Windows | Registers Folder Sync under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` for your user only. No admin rights are needed. |

## System tray

Closing the window hides Folder Sync to the tray, and syncing continues. Click the tray icon to reopen the window. Right-click it for **Open / Settings / About / Exit**. Only **Exit** stops the app.

## Where data is stored

| File | Location |
|---|---|
| Database (pairs and settings) | `%LOCALAPPDATA%\FolderSync\folder_sync.db` |
| Log file (rotating, 3 × 1 MB) | `%LOCALAPPDATA%\FolderSync\folder_sync.log` |

To reset Folder Sync completely, exit it and delete that folder.

## Troubleshooting

| Symptom | Fix |
|---|---|
| *Folder unavailable* | One of the folders does not exist, or a drive or network share is disconnected. Reconnect it and start the pair again. |
| *Skipped locked file* | Another program had the file open. It syncs the next time the file changes. You can also click **Start Pair** to run a full mirror. |
| Changes were made while Folder Sync was closed | Click **Start Pair** to run a full mirror. |
| Windows SmartScreen warning | The executable is not code-signed. Choose **More info → Run anyway**, or build from source. |
