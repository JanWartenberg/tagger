# 01 — Complete Indexed Reverse-Search Result Mode

Status: ready-for-agent
Category: feature
Priority: medium
Blocked by: None

## Goal

Make a database query show every matching photo from the active root's SQLite index as a temporary, usable Photo Workspace view, then restore the exact prior folder view when the user leaves search.

## Acceptance Criteria

- [ ] A completed current search can show indexed matches that are not currently loaded in the Photo Workspace.
- [ ] Starting search leaves the prior view usable until the current background result applies atomically.
- [ ] Search-result mode preserves the prior folder view's paths, selected paths, active path, and Qt scroll position for restoration.
- [ ] `:search <query>` runs the existing `tag:`, `date:`, or bare-tag query; `Esc`, `:back`, `:clearsearch`, and the Clear control restore the prior folder view.
- [ ] Result paths support normal selection, preview, metadata reads, and tag mutations.
- [ ] Replacing the workspace, clearing search, or starting a newer query rejects obsolete search completions.
- [ ] Folder mode remains the default; search never deletes or mutates the prior folder membership merely by being entered.

## Scope

- Evolve the Photo Workspace database-search interface so its result view can contain indexed paths outside current folder membership while retaining one complete logical restoration state.
- Keep SQLite reads behind the existing background coordinator; retain its request identity and stale-result rules.
- Register the search/back commands through the action catalogue and preserve existing search textbox shortcuts.
- Render restored Qt scroll position in MainWindow without moving logical scroll state into Photo Workspace.

## Tests

- Add pure Photo Workspace tests for external indexed results, result selection, search replacement, clear/back restoration, and stale completion rejection.
- Add offscreen adapter coverage for `:search`, `:back`, result usability, source-view restoration, and stale asynchronous results.

## Validation

- `ruff check --no-cache photo_workspace.py exif_ui.py actions.py tests/test_photo_workspace_search.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache photo_workspace.py exif_ui.py actions.py tests/test_photo_workspace_search.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`
