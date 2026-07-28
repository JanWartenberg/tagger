# 01 — Add Persistent Files-Pane View Indicator

Status: completed
Category: feature
Priority: medium
Blocked by: None

## Goal

Make the active Photo Workspace scope visible above the image-files pane for folder, IPTC-empty, and database-search views.

## Acceptance Criteria

- [x] The files pane persistently displays `Folder view · <count> photos` in normal folder mode.
- [x] It displays IPTC-empty scan progress while the scan is running and a labelled IPTC-empty count after the atomic view transition.
- [x] It displays the current query while an index search is pending, then the query, result count, and `:back` guidance for an accepted search-result view.
- [x] Clear, `:back`, Escape, folder replacement, failures, and stale/superseded completions cannot leave stale search or filter wording visible.
- [x] The footer may retain transient feedback but is not the only active-view cue.
- [x] The implementation derives logical state from `PhotoWorkspaceSnapshot` and existing request identities; it introduces no parallel logical view/filter state.

## Scope

- Reuse or rename the existing `filterInfoLabel` above the files pane.
- Add one focused MainWindow presentation helper that maps the current snapshot plus current request/query facts to label text.
- Invoke it from current rendering, IPTC-filter, database-search, clear/back/Escape, and workspace-replacement transitions.
- Preserve the existing action catalogue, background-coordinator, and Photo Workspace interfaces unless a small presentation field is demonstrably needed.

## Tests

- Add offscreen coverage for folder, pending/completed IPTC-empty, pending/completed search, clear/back/Escape restoration, and stale completions.
- Assert label text through the visible widget.

## Validation

- `ruff check --no-cache exif_ui.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache exif_ui.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`

## Comments

Completed with one MainWindow presentation helper that derives indicator text from the current `PhotoWorkspaceSnapshot`, accepted search request, and accepted search query. Offscreen adapter coverage verifies normal, IPTC-empty pending/completed, search pending/completed, clear/back/Escape, failed search/filter, workspace replacement, and superseded search behavior.

Validation passed:

- `ruff check --no-cache exif_ui.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache exif_ui.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (101 tests)
- `git diff --check`
