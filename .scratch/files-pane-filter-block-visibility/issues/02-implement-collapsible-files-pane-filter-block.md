# 02 — Implement Collapsible Files-Pane Filter Block

Status: completed
Priority: medium
Category: feature
Milestone: M5 — Composable workspace filtering
Blocked by: 01

## Goal

Let the user collapse the Files-pane filter inputs to reclaim space without hiding active conditions or changing Photo Workspace state.

## Product Contract

- The filter block starts open on every application launch. Visibility is not persisted and remains unchanged across Photo Workspace changes during the running session.
- Add a compact, always-visible toggle at the right of the top Files-pane row. Use Qt standard down/right arrows for open/collapsed state and action-oriented tooltip and accessible names: `Hide filters` and `Show filters`.
- Register the toggle in the action catalogue as command `:togglefilters` with global shortcut `Ctrl+Shift+F`.
- Collapse only the bordered filter input/action frame. Active-condition chips, workspace/result information, loading progress, and Files-pane messages remain visible.
- Preserve hidden drafts and validation state. Pending filename debounce and all running background operations continue normally.
- If a focused filter child is hidden, focus the Files-pane photo list without changing selection or active photo. Existing field-focus actions first open a hidden block and then focus/select their target. Escape retains its current field-specific behavior and never collapses the block.
- Render Tags, Date, IPTC-empty, Filename, and each directory exclusion as individually removable, keyboard-focusable chips. Enter or Space removes the focused condition. After removal, focus the next chip if present, otherwise the previous chip, otherwise the photo list.
- Removing Tags or Date preserves and reapplies the other indexed-search component when present. Every other chip clears only the condition it represents.
- Tab and Shift+Tab include the toggle and active chip buttons in normal keyboard traversal. Contextual filter-frame shortcuts need not work while their owner frame is hidden.

## Ownership

`MainWindow` owns this presentation state. The Photo Workspace continues to own filter conditions and derived membership. Toggling visibility must not alter conditions, membership, selection, active photo, scroll restoration, or stale-result handling.

## Acceptance Criteria

- [x] Initial state is open even after restarting the application; no visibility setting is read or written.
- [x] Button, `:togglefilters`, and `Ctrl+Shift+F` toggle the same state and update arrow, tooltip, and accessible name.
- [x] A Photo Workspace replacement preserves the current in-session visibility.
- [x] Collapsing hides only filter inputs/actions; active chips, counts/status, progress, and empty-result messages remain visible.
- [x] Collapsing from a focused child moves focus to the unchanged photo selection; each global field-focus action reopens and focuses its target.
- [x] Escape behavior, hidden drafts/errors, filename debounce, and running background work are preserved.
- [x] Every active condition can be removed independently by mouse, Enter, or Space; combined Tags/Date search preserves the component not removed.
- [x] Chip focus advances deterministically after removal and reaches the photo list after the last chip.
- [x] The toggle remains visible and usable under narrow-window and offscreen test layouts.
- [x] No synchronous filesystem, SQLite, ExifTool, or image work is added.

## Suggested Test Locations

- `tests/test_main_window_characterization.py` for visibility, action catalogue, focus, chip removal, combined Tags/Date behavior, workspace transitions, and narrow/offscreen rendering.

## Validation

- `ruff check --no-cache actions.py exif_ui.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache actions.py exif_ui.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_main_window_characterization -v`
- `git diff --check`

## Constraints

- Do not persist visibility or move it into `PhotoWorkspace`.
- Do not change query grammar, matching semantics, index schema, discovery, or filter-condition persistence.
- Do not conceal an active condition or require a mouse to recover or remove it.

## Completion

Implemented and accepted in `aad1ec8`. The follow-up NoTags query performance fix was accepted in `7ef8243`. Full validation passed with 234 tests.
