# 01 — Preserve Scroll During Filtered Files-Pane Selection

Status: completed
Priority: high
Category: bug
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Keep the Files-pane viewport stable when selecting an already visible photo in an active No tags view, while preserving normal keyboard navigation to a photo outside the viewport.

## Cause

The No tags view keeps all workspace rows in `QListWidget` and hides non-matches. On Windows, `setCurrentRow()` can queue an `ensure-visible` scroll after the selection signal. The previous unconditional `scrollToItem()` in `j`/`k` navigation compounded that behavior: moving between the first two visible photos moved the viewport, and `k` at the first visible photo could scroll despite retaining selection.

## Delivered

- [x] Capture the pre-selection Files-pane scroll anchor for a mouse click or keyboard move to an already visible item.
- [x] Restore that anchor with an owned one-shot Qt timer after delayed `QListWidget` scrolling has run.
- [x] Scroll keyboard navigation only when its target was outside the prior viewport.
- [x] Keep `gg`/`G` edge navigation explicitly scrolling to its selected visible edge.
- [x] Add deterministic offscreen regressions for delayed native-scroll simulation after mouse selection and `j → k → k` in an active No tags view.
- [x] Preserve the viewport during extended selection with `Shift+J/K` and `Shift+Up/Down`; route both shortcut pairs through the same protected selection path.

## Validation

- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests` — 261 tests passed.
- `ruff check --no-cache exif_ui.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache exif_ui.py tests/test_main_window_characterization.py`
- `git diff --check`

## Constraints

- `PhotoWorkspace` remains the owner of logical selection and visible membership.
- `MainWindow` owns Qt pixel scroll state, event ordering, and timers.
- Preserve click selection, preview/metadata loading, filtered keyboard navigation, and explicit filter-transition scroll restoration.
