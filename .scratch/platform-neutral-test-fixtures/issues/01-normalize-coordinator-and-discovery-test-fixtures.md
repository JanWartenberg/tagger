# 01 — Normalize Coordinator and Discovery Test Fixtures

Status: completed
Category: bug
Blocked by: None

## Goal

Make deterministic Coordinator and MainWindow discovery fixtures platform-neutral by configuring and asserting normalized paths.

## Acceptance Criteria

- [x] `tests/test_background_coordinator.py` uses normalized fixture values wherever the Coordinator normalizes a root or path.
- [x] Affected folder/drop tests in `tests/test_main_window_characterization.py` configure fake discovery with the normalized root the adapter receives.
- [x] The full Coordinator test module passes on Windows and Linux.
- [x] The full MainWindow characterization module no longer has discovery/path failures on Windows.

## Validation

- `python -m unittest discover -s tests -p test_background_coordinator.py -v`
- `python -m unittest discover -s tests -p test_main_window_characterization.py -v`
- `git diff --check`

## Diagnosis

The Windows acceptance run normalized `/photos` to `C:\photos` before fake-adapter lookup. The fakes were keyed by the original POSIX literals, producing `KeyError`-derived discovery failures and empty index results.

Implemented with normalized test-fixture paths and a normalizing fake discovery-result mapping. Linux validation passed:

- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_background_coordinator.py -v` (17 tests)
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_main_window_characterization.py -v` (47 tests)
- Ruff check/format and `git diff --check`

Windows validation completed: the full offscreen suite passed with 109 tests.
