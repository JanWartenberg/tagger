# Complete the Photo Workspace adapter migration

Status: completed
Blocked by: 04

## Goal

Finish the behavior-preserving migration and remove superseded Photo Workspace state and rules from `MainWindow`.

## Acceptance criteria

- `MainWindow` is a thin Qt adapter: it forwards intent, schedules external work, renders snapshots, and owns Qt-only state (focus, scrollbars, widgets, workers, timers, signal wiring, dialogs).
- `PhotoWorkspace` owns all state named in the refactor spec: identities, ordering, mode, visibility, ordered selection, active-photo rule, logical restoration state, filter progress, batches, and stale-result acceptance.
- The old parallel state fields and duplicate transition logic are removed rather than retained as fallbacks.
- Existing launcher, controls, keyboard/mouse behavior, commands, persistence formats, ExifTool behavior, and status/error behavior remain materially unchanged.
- New and modified Python passes Ruff without broadly reformatting unrelated code.
- Pure tests pass in Linux; Windows offscreen integration acceptance passes.

## Comments

- Consolidated the workspace view into one explicit mode and exposed that mode in rendering snapshots; legacy active-filter/search flags are now derived from it.
- Made the Qt adapter consume workspace visibility and filter state for file navigation, tag mutations, and selection repair rather than reading widget visibility or checkbox state as a parallel model.
- Corrected the tag-completion characterization expectation to the application's existing case-insensitive sorted display order.
- Validation: `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` passed (29 tests) on Linux. The available system PyQt6 is 6.4.2, below the declared `PyQt6>=6.6` dependency minimum; a project environment meeting that requirement could not be created because `ensurepip`/`python3-venv` is unavailable in this container. `RUFF_CACHE_DIR=/tmp/tagger-ruff-cache ruff check exif_ui.py photo_workspace.py tests/test_main_window_characterization.py tests/test_photo_workspace_search.py`, `ruff format --check` for those files, `python3 -m compileall -q photo_workspace.py exif_ui.py tests`, and `git diff --check` passed. Windows offscreen acceptance later completed with 109 passing tests; the evidence is recorded in `.scratch/windows-offscreen-acceptance/issues/01-run-current-windows-offscreen-suite.md`.

## Out of scope

- The deferred backlog items: frozen-snapshot filtering, complete reverse search, tag-mutation redesign, action-dispatch redesign, and broad cleanup.
