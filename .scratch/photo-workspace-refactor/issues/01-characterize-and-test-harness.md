# Characterize Photo Workspace behavior and establish the test harness

Status: completed

## Goal

Capture the current Photo Workspace behavior before changing ownership, and establish the repository's first test conventions.

## Scope

- Establish the pure-`unittest` test location and conventions for the behavior that will move into `PhotoWorkspace`; ticket 02 adds those tests when the seam exists.
- Derive expected results from the current executable behavior, not from `INDEXING_PLAN.md`.
- Add a minimal Windows/offscreen PyQt integration harness using fakes for ExifTool and indexing dependencies.
- Document the commands for pure Linux tests and Windows Qt tests.

## Acceptance criteria

- The documented pure-test conventions require neither PyQt, ExifTool, SQLite, real photos, nor background threads.
- Ticket 02 must add pure tests covering normalized-path identity assumptions, insertion order, duplicate suppression, reload clearing, ordered multi-selection, active-photo choice, visibility changes, empty visible results, one-step IPTC-empty preservation, filter progress, stale-result rejection, search-match application, search clearing, and failed-filter preservation.
- The Qt harness verifies only adapter wiring: widget intent reaches the model, model state renders into the Photo Workspace, hidden selection is repaired, and public main-window methods stay callable.
- Tests and the required Windows acceptance command are recorded in the issue comments.

## Out of scope

- Moving production state into a new module.
- Changing any current UI behavior.

## Comments

- The current UI has no Qt-free Photo Workspace seam. Ticket 02 introduces it; its pure `unittest` coverage will exercise the behavior cases listed above.
- The Qt adapter characterization suite and its fake ExifTool/index adapters are in `tests/test_main_window_characterization.py`.
- Linux command run: `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` — passed (29 tests) with the available PyQt6 installation.
- Windows acceptance command: `set QT_QPA_PLATFORM=offscreen && python -m unittest discover -s tests -v` (still to be run in the Windows project environment).
