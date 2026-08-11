# 01 — Isolate Persisted State in MainWindow Tests

Status: completed
Category: bug
Blocked by: None

## Goal

Remove dependence on a developer's persisted TAGGER data from MainWindow characterization tests.

## Acceptance Criteria

- [x] Test setup supplies empty or explicitly configured recent-tag and config state before constructing `MainWindow`.
- [x] Autocomplete assertions use only their fake index snapshot.
- [x] `test_escape_hides_tag_completion_and_exits_tag_input` has deterministic completion candidates.
- [x] Production `storage.py` behavior remains unchanged.

## Validation

- `python -m unittest discover -s tests -p test_main_window_characterization.py -v`
- `git diff --check`

## Diagnosis

The Windows run loaded a persisted `Birdrace` recent tag, which appeared in the autocomplete candidate list. The tests did not isolate application storage.

Implemented by patching all storage functions imported by `exif_ui` before each `MainWindow` construction: loads receive empty state and save operations cannot touch user storage. Linux validation passed:

- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_main_window_characterization.py -v` (47 tests)
- Ruff format check and `git diff --check`

Windows validation completed: the full offscreen suite passed with 109 tests, including deterministic autocomplete coverage.
