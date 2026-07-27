# 02 — Index Freshness and Manual Reindexing

Status: completed
Category: feature
Priority: medium
Blocked by: None

## Goal

Make the active-root SQLite index refresh predictably in the background and give the user an explicit `:reindex` command for a full refresh.

## Acceptance Criteria

- [x] TAGGER records the last successful index refresh and starts a background incremental refresh when an active root's index is more than 24 hours old.
- [x] A stale active-root index refresh runs without blocking the UI and does not delay a usable folder view.
- [x] `:reindex` starts a background full reindex of the active root and gives concise non-modal progress and completion/failure feedback.
- [x] A refresh removes rows for photos deleted from the filesystem and updates changed metadata while preserving current query behavior.
- [x] Full reindex work uses the existing coordinator's per-root serial write queue and cannot overlap writes for that root.
- [x] A stale, superseded, or departed-root completion cannot alter the current workspace or overwrite more relevant footer feedback.

## Scope

- Extend the index/coordinator seam with index freshness metadata and full-refresh intent as needed.
- Reuse existing background discovery, index adapters, and per-root write serialization; do not add a thread pool or run filesystem/SQLite work from UI callbacks.
- Register `:reindex` through the action catalogue.

## Tests

- Add deterministic coordinator tests for stale-index scheduling, full-refresh queue ordering, deletion cleanup, and failure continuation.
- Add offscreen adapter coverage for `:reindex` feedback and rejection of stale/departed-root completions.

## Validation

- `ruff check --no-cache actions.py exif_ui.py indexing.py services/background_coordinator.py tests/test_indexing.py tests/test_background_coordinator.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache actions.py exif_ui.py indexing.py services/background_coordinator.py tests/test_indexing.py tests/test_background_coordinator.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`

## Comments

Completed with a 24-hour `last_index_scan` freshness check, serial automatic/manual root refresh operations, and the catalogue-backed `:reindex` command. Refresh events carry request identity and workspace generation so stale or departed-root completions cannot replace current feedback.

Validation: `ruff check` passed for all modified Python files; `ruff format --check` passed for every modified file except `actions.py`, whose pre-existing HEAD content already fails that formatter check and was intentionally not broadly reformatted. `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` passed (96 tests), and `git diff --check` passed.
