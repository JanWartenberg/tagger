# 01 — Pending and Failed Single-Photo Mutations

Status: completed
Category: bug
Priority: high
Blocked by: None — can start immediately

**What to build:**

When a user adds or removes tags for one photo, TAGGER must immediately show the requested metadata as a Pending tag mutation without blocking further interaction. The affected photo-files-pane entry and its detail area must distinguish pending metadata from confirmed metadata. A successful write confirms the change; a failed write restores the Confirmed metadata state and leaves a persistent, visible failed state.

- [x] A single-photo tag add or remove is visibly pending immediately, while the UI remains interactive.
- [x] Pending and failed states are visible in both the affected photo-files-pane entry and selected-photo detail area.
- [x] A successful write alone confirms metadata; only confirmed state updates the index, while the current IPTC-empty filter view remains stable until the user reactivates it.
- [x] A failed write restores the last Confirmed metadata state rather than presenting requested tags as file truth.
- [x] Pure mutation-coordination tests and offscreen adapter tests cover pending, success, and failure behavior.

## Validation

- `ruff check --no-cache .`
- `ruff format --check --no-cache exif_ui.py photo_workspace.py services/pending_tag_mutation.py tests/test_pending_tag_mutations.py tests/test_main_window_characterization.py tests/test_photo_workspace_filter.py`
- `python3 -m compileall -q exif_ui.py photo_workspace.py services/pending_tag_mutation.py tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (34 passed)
- `git diff --check`
