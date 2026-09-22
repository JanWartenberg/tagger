# Test conventions

TAGGER uses built-in `unittest` tests at two seams:

1. **Core and coordinator tests** exercise `PhotoWorkspace`, tag-mutation,
   indexing, and background-coordinator behavior without constructing Qt widgets.
   The Photo Workspace tests must not import PyQt, ExifTool, SQLite, filesystem
   code, or worker code.
2. **Qt adapter tests** in `test_main_window_characterization.py` run `MainWindow`
   offscreen through public entrypoints and widget events. They use fake ExifTool,
   index, discovery, and background-runner adapters; they must not access a real
   photo library or create a production index database.

## Requirements

Install the project dependencies before running the complete suite:

```sh
python3 -m pip install -r requirements-dev.txt
```

`requirements.txt` requires `PyQt6>=6.6`. When PyQt6 is installed, test discovery
runs both the core/coordinator tests and the Qt adapter tests. If PyQt6 is absent,
only `test_main_window_characterization.py` is skipped; the remaining tests still
run.

## Commands

Linux and other POSIX environments:

```sh
QT_QPA_PLATFORM=offscreen python3 -m pytest
```

Windows Command Prompt (`cmd.exe`), from the activated project virtual environment:

```bat
set QT_QPA_PLATFORM=offscreen
pytest
```

Windows PowerShell:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
pytest
```

## Acceptance

A successful local Linux offscreen run validates the available core and Qt adapter
coverage, but it does not replace Windows acceptance. Run and record the Windows
command before accepting a change that affects the Qt adapter or Windows workflow.
