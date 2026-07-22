# 01 — Make IPTC-Empty Filter View Transitions Atomic

Status: completed
Category: bug
Priority: medium
Blocked by: None

## Goal

Make every IPTC-empty filter transition describe one coherent Photo Workspace view. A pending or failed filter must never expose partial paths or a mode/checkbox that disagrees with the visible view.

## Acceptance Criteria

- [x] Starting a filter captures the source normal or database-search view, including visible paths, selection, and active path; the source view remains visible while scanning and the checkbox remains unchecked.
- [x] Filter batches do not progressively replace the files pane. Only a completed successful result applies atomically.
- [x] A successful result enters IPTC-empty mode, checks the checkbox, and selects the first matching photo. A successful empty result is checked with no selection.
- [x] A failure discards all partial results, restores the captured source mode, paths, selection, and active path, and leaves the checkbox unchecked.
- [x] The Qt adapter scrolls the restored selected photo to the top after failure and after clearing a successful filter.
- [x] Clearing a successful filter restores its captured source view, including database-search results when applicable.
- [x] Rechecking after failure starts a fresh filter operation; there is no automatic or separate retry.
- [x] Stale filter completions cannot alter the current view or checkbox state.

## Scope

- Keep view-state, restoration, and stale-result rules in `PhotoWorkspace`.
- Keep worker scheduling, non-modal failure feedback, checkbox rendering, and physical scrolling in `MainWindow`.
- Preserve the existing frozen active-filter membership rule after a successful result.

## Tests

- Add pure transition tests for normal and database-search source views across pending, success, empty success, failure, clear, restart, and stale-completion paths.
- Add offscreen adapter coverage for source-view retention during scanning, checkbox state, atomic completion, and scroll-to-restored-selection behavior.

## Validation

- `ruff check --no-cache photo_workspace.py exif_ui.py tests/test_photo_workspace_filter.py tests/test_photo_workspace_search.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache photo_workspace.py exif_ui.py tests/test_photo_workspace_filter.py tests/test_photo_workspace_search.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`

## Comments

Completed with atomic source-view restoration in `PhotoWorkspace` and offscreen adapter coverage for checkbox rendering, non-modal failure feedback, and scrolling restored selections.

Validation completed:

- `ruff check --no-cache photo_workspace.py exif_ui.py tests/test_photo_workspace_filter.py tests/test_photo_workspace_search.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache photo_workspace.py exif_ui.py tests/test_photo_workspace_filter.py tests/test_photo_workspace_search.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (80 tests)
- `git diff --check`
