# 01 — Close PhotoIndex Connections Deterministically

Status: completed
Category: bug
Blocked by: None

## Goal

Prevent SQLite connection leaks and Windows temporary-file locks in `PhotoIndex`.

## Acceptance Criteria

- [x] Every connection opened by `PhotoIndex` closes on normal return and exception.
- [x] Existing commit/rollback behavior for writes and migrations remains correct.
- [x] `tests/test_indexing.py` completes on Windows without `WinError 32` cleanup failures or unclosed-database warnings.
- [x] Existing index search, batching, migration, and refresh assertions remain green.

## Validation

- `python -m unittest discover -s tests -p test_indexing.py -v`
- `ruff check --no-cache indexing.py tests/test_indexing.py`
- `ruff format --check --no-cache indexing.py tests/test_indexing.py`
- `git diff --check`

## Diagnosis

The Windows acceptance run reported six `WinError 32` failures while deleting temporary `.tagger/index.sqlite` files and emitted `ResourceWarning: unclosed database`. Python's sqlite connection context manager does not close the connection.

Implemented with `PhotoIndex._connection()`, which commits on success, rolls back on failure, and always closes in `finally`. Every former `with self._connect()` caller now uses this lifecycle seam. Added direct success/failure lifecycle coverage. The two legacy-schema test fixtures also now close their direct `sqlite3.connect()` handles; those test handles caused the remaining Windows locks after the PhotoIndex fix.

Linux validation passed:

- `python3 -m unittest discover -s tests -p test_indexing.py -v` (8 tests)
- Ruff check/format and `git diff --check`

Windows validation completed: the full offscreen suite passed with 109 tests, without `WinError 32` cleanup failures or unclosed-database warnings.
