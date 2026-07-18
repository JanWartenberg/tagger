# Test conventions

The Photo Workspace refactor uses two seams:

1. **PhotoWorkspace interface** — pure built-in-`unittest` tests exercise intent-level operations and immutable rendering snapshots. These tests must not import PyQt, ExifTool, SQLite, filesystem code, or worker code. Ticket 02 introduces this interface and its pure tests.
2. **Qt adapter** — offscreen tests exercise `MainWindow` through widget events and public entrypoints. They use fake ExifTool and index adapters; they must not invoke ExifTool, access a real photo library, or create an index database.

## Commands

Linux (the Qt suite is skipped when PyQt6 is unavailable):

```sh
python3 -m unittest discover -s tests -v
```

Windows (run from the activated project virtual environment):

```bat
set QT_QPA_PLATFORM=offscreen
python -m unittest discover -s tests -v
```

Run the Windows command before accepting any Photo Workspace refactor slice. The Linux agent environment currently lacks PyQt6, so it can run only the future pure `PhotoWorkspace` suite.
