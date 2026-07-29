# 01 — Run Current Windows Offscreen Acceptance Suite

Status: completed
Category: validation
Blocked by: None

## Goal

Verify the current unit suite in TAGGER's Windows project environment and close the recorded Windows-acceptance gap with evidence.

## Acceptance Criteria

- [x] The current offscreen suite runs from the activated Windows project environment.
- [x] The command, Python/PyQt environment, and result are recorded below.
- [x] Historical tickets that explicitly marked this acceptance as outstanding are updated to completed acceptance.

## Comments

Created while reconciling historical completion records.

Windows run recorded: `QT_QPA_PLATFORM=offscreen; python -m unittest discover -s tests -v` on Python 3.14 failed with **20 failures and 7 errors**.

- Coordinator and discovery tests passed POSIX-style fixture paths into code that normalizes paths as Windows paths, so fake-adapter lookups missed.
- Indexing tests left SQLite connections open; Windows then could not delete temporary `index.sqlite` files (`WinError 32`), accompanied by `ResourceWarning` messages.
- Two MainWindow tests observed a persisted recent tag (`Birdrace`), showing that they read user storage rather than isolated test state.

The font and `propagateSizeHints` messages are warnings, not recorded test failures. The following fixes are implemented; rerun the suite to complete acceptance:

- `.scratch/platform-neutral-test-fixtures/issues/01-normalize-coordinator-and-discovery-test-fixtures.md`
- `.scratch/sqlite-connection-lifecycle/issues/01-close-photo-index-connections-deterministically.md`
- `.scratch/main-window-test-storage-isolation/issues/01-isolate-persisted-state-in-main-window-tests.md`

Linux offscreen validation passed with 109 tests after all three fixes.

Windows validation completed with `cmd /c "set QT_QPA_PLATFORM=offscreen&& python -m unittest discover -s tests -v"`: 109 tests passed in 3.776 seconds. The environment used Python 3.14 with PyQt6 6.10.2, PyQt6-Qt6 6.10.1, and PyQt6_sip 13.11.
