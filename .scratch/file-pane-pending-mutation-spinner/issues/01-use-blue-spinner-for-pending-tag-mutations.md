# 01 — Use Blue Spinner for Pending Tag Mutations

Status: completed
Category: enhancement
Priority: low
Blocked by: None

## Goal

Replace the static reload icon on a pending file-pane entry with the existing blue animated loading-spinner treatment.

## Acceptance Criteria

- [x] A queued or in-flight tag mutation displays the blue animated spinner beside every affected file-pane entry.
- [x] Multiple pending entries animate correctly without one permanent widget/timer per row.
- [x] Confirmation, failure, departure from the Photo Workspace, and rerendering remove the pending spinner promptly.
- [x] The spinner uses the shared file-pane status-marker position; an unverified-IPTC `?` marker returns after the mutation settles.
- [x] Failed mutations retain the existing non-spinning attention indicator and `:retry` guidance.
- [x] File-pane selection, keyboard navigation, and large-workspace batch rendering remain intact.
- [x] Offscreen tests cover pending, success, failure, and workspace replacement rendering transitions.

## Implementation Direction

Reuse the visual treatment of `LoadingSpinner` in `exif_ui.py`. The rendering technique is an implementation detail, but it must use TagMutationCoordinator lifecycle state and must not turn every file-pane row into a permanent animated widget.

## Validation

- Run Ruff on modified Python files.
- Run the focused mutation and MainWindow characterization tests, then the complete offscreen suite.
- Run `git diff --check`.

## Completion

Implemented by sharing LoadingSpinner's blue arc painter with a one-timer file-pane icon animation. The MainWindow characterization test verifies that the pending icon advances frames and existing pending, success, failure, and workspace-replacement coverage verifies lifecycle cleanup.

Validation:

- `ruff check exif_ui.py tests/test_main_window_characterization.py`
- `ruff format --check exif_ui.py tests/test_main_window_characterization.py`
- `python3 -m compileall -q exif_ui.py tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (169 tests)
- `git diff --check`.
