# Introduce PhotoWorkspace for membership and selection

Status: completed
Blocked by: 01

## Goal

Introduce the plain-Python `PhotoWorkspace` module and move Photo Workspace identity, insertion order, membership, visible selection, and active-photo rules into it.

## Interface direction

Use one mutable `PhotoWorkspace` object. Its interface accepts intent-level operations (add paths, reload paths, select paths) and exposes immutable rendering snapshots/results. It must not expose mutable internal collections or import Qt.

## Acceptance criteria

- The module lives in the repository's flat module structure and imports no Qt, ExifTool, SQLite, filesystem, or worker code.
- It accepts normalized path identities, preserves insertion order, and ignores duplicate adds; the Qt adapter normalizes filesystem input before passing it in.
- Reload clears prior Photo Workspace membership and state before accepting discovered paths.
- Selection is ordered by display order; the first visible selected photo is active.
- A visibility change that hides the active selection chooses the same replacement behavior as the current application; no visible result clears selection.
- `MainWindow` becomes a Qt adapter for membership and selection, while its public-looking entrypoints remain callable.
- Add the pure `unittest` behavior coverage established by ticket 01; the Windows adapter tests remain green.

## Out of scope

- IPTC-empty filtering, search-result restoration, metadata reads, and worker scheduling.

## Comments

- Implemented by `photo_workspace.py`; `MainWindow` now adapts membership and selection through this module.
- Pure test command run: `python3 -m unittest tests/test_photo_workspace.py -v` (5 passing tests).
- Full suite command run: `python3 -m unittest discover -s tests -v` (5 passing pure tests; 3 Qt tests skipped because PyQt6 is unavailable in the agent environment).
- Windows offscreen acceptance completed with 109 passing tests; the evidence is recorded in `.scratch/windows-offscreen-acceptance/issues/01-run-current-windows-offscreen-suite.md`.
