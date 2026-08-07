# File-Pane Pending-Mutation Spinner

Status: completed
Priority: low

## Problem Statement

A pending tag mutation currently shows a static reload icon beside its photo in the file pane. TAGGER already has a blue animated loading spinner for folder and large-workspace loading; pending writes should use that same visual language.

## Desired Outcome

Every file with a pending tag mutation shows the existing blue animated spinner beside its file-pane entry until the mutation reaches a confirmed or failed lifecycle state.

## Scope

- Use the existing LoadingSpinner visual treatment beside each pending file-pane entry; do not introduce a second spinner design or image asset.
- Cover queued and in-flight mutations, including multiple pending photos.
- Remove the spinner immediately when a mutation succeeds, fails, is discarded after a workspace change, or its row is rerendered without a pending state.
- The spinner occupies the shared file-pane status-marker position. It temporarily takes precedence over an unverified-IPTC `?` marker, which returns when the mutation settles.
- Keep the existing failed-mutation attention indicator and retry guidance; failed entries do not spin.
- Preserve file-pane selection, keyboard navigation, large-workspace batch rendering, and the existing detail-area pending/failed wording.

## Constraints

- The TagMutationCoordinator remains the source of pending/failed state; this is rendering-only work.
- Do not create one permanent widget or timer per file-pane row. Animate only while pending entries exist and avoid unnecessary repaint work for a large workspace.
- Keep the spinner blue and visually consistent with the existing folder/workspace loading spinner.

## Testing

- Add offscreen coverage that a pending row uses the pending-spinner rendering and that success, failure, and workspace replacement remove it.
- Preserve existing pending/failed mutation, selection, and large-workspace rendering tests.

## Completion

Implemented with one shared 16 ms timer and frame icon for only pending rows; no per-row widget or timer is created. `LoadingSpinner` and the file-pane frame renderer share the same blue arc painter.

Validation:

- `ruff check exif_ui.py tests/test_main_window_characterization.py`
- `ruff format --check exif_ui.py tests/test_main_window_characterization.py`
- `python3 -m compileall -q exif_ui.py tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (169 tests)
- `git diff --check`

## Out of Scope

- Changing tag-mutation scheduling, retry behavior, or failure semantics.
- Changing the folder/workspace loading spinner behavior.
