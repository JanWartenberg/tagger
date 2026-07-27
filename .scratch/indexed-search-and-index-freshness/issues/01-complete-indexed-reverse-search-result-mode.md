# 01 — Complete Indexed Reverse-Search Result Mode

Status: completed
Category: feature
Priority: medium
Blocked by: None

## Goal

Make a database query show every matching photo from the active root's SQLite index as a temporary, usable Photo Workspace view, then restore the exact prior folder view when the user leaves search.

## Acceptance Criteria

- [x] A completed current search can show indexed matches that are not currently loaded in the Photo Workspace.
- [x] Starting search leaves the prior view usable until the current background result applies atomically.
- [x] Search-result mode preserves the prior folder view's paths, selected paths, active path, and Qt scroll position for restoration.
- [x] `:search <query>` runs the existing `tag:`, `date:`, or bare-tag query; `Esc`, `:back`, `:clearsearch`, and the Clear control restore the prior folder view.
- [x] Result paths support normal selection, preview, metadata reads, and tag mutations.
- [x] Replacing the workspace, clearing search, or starting a newer query rejects obsolete search completions.
- [x] Folder mode remains the default; search never deletes or mutates the prior folder membership merely by being entered.

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

## Implementation Design

### State ownership and interfaces

- Keep `PhotoWorkspace` as the deep module at the logical-view seam. It owns the active result view and one immutable folder-view restoration state: ordered paths, selected paths, and active-path derivation. It must never discard or mutate that folder state merely because a search result is shown.
- A completed first search replaces the active workspace paths with all normalized paths returned by the active root's index, including paths absent from the currently loaded folder paths. This makes result paths normal workspace members, so existing selection, preview, metadata read, and tag-mutation flows operate without a second result-specific path mechanism.
- The first completed search captures the folder restoration state. A later query while already in search mode replaces only the active result paths; it retains that original restoration state. `clear_database_search()`/back restores the complete captured folder state and then clears it.
- Beginning a search leaves the current rendered view untouched. Only the current background completion performs the atomic transition into result mode. An empty current result is a valid empty result view and is still restorable.
- Entering result mode cancels any in-progress IPTC-empty filter through the existing workspace operation invalidation. Search restoration returns to the captured folder view, not to a partially completed or completed IPTC-empty filter view.
- `PhotoWorkspaceSnapshot.paths` represents the active logical view's paths. Its existing ordered `visible_paths`, selection repair, and active-path rule remain the sole rendering contract; no parallel result-path collection belongs in `MainWindow`.

### Qt adapter and command routing

- Keep SQLite queries behind `BackgroundCoordinator.search_index()` and retain its request identity plus workspace-generation checks. `MainWindow` accepts only the active request for the active root, rejects stale/superseded/departed-root events, and clears its active-request reference once the accepted result applies.
- Register a `search` `ActionSpec` with a command argument contract. `:search <query>` uses the entire text following the command as the existing query syntax (`tag:`, `date:`, or bare tag), mirrors it into the search field, and schedules the existing background read. Do not create parallel command dispatch or direct SQLite calls.
- Make `back` an alias of the existing clear-search action. `:back`, `:clearsearch`, the Clear control, and `Esc` when the command line and text inputs are not handling Escape all perform the same restoration transition. Existing Escape behavior still takes precedence for closing the command line and leaving text entry.
- `MainWindow` remains the Qt-only adapter for scroll state. Immediately before the first accepted search transition, it captures a files-pane anchor (top source path and pixel offset). On restoration it renders the restored workspace snapshot and reapplies that anchor. Replaced searches do not overwrite the captured folder scroll state.
- Workspace replacement, explicit clearing/back, and newer searches invalidate obsolete reads through the existing coordinator. A folder replacement also discards the logical restoration state and its Qt scroll anchor.

### Delivery slices

1. Evolve the Photo Workspace interface and pure tests for external result paths, one-level restoration, replacement searches, empty results, filter invalidation, and source-state preservation.
2. Adapt rendering and the tag-mutation workspace membership transition so result paths are fully usable. Add the Qt scroll-anchor capture/restore at the adapter seam.
3. Add the catalogue-backed `:search` command and `:back` alias, integrate Escape precedence, and preserve the search textbox workflow.
4. Add deterministic/offscreen coverage for current versus stale reads, result selection/metadata/tagging, command and Clear/Escape restoration, source scroll restoration, and workspace replacement during a request or result view.

### Clarification Assessment

No product decision blocks implementation. The following implementation decisions are now fixed by this ticket preparation:

- Search is scoped to the already active index root; it is not global or cross-root.
- A result view is temporary and has one restoration level. Replacing a query does not create nested back states.
- Search entered while an IPTC-empty filter is active restores the underlying folder view, not the filter result.
- `:search` preserves whitespace after the command as part of the query; quoted-shell parsing is not introduced.
- Index freshness and missing/deleted files remain the responsibility of ticket 02. This ticket reports existing metadata/preview errors normally and does not repair the index.

## Comments

Completed with external indexed result paths, one-level folder restoration, source scroll restoration, and catalogue-backed `:search`/`:back` commands.

Validation: `ruff check` passed for all modified Python files; `ruff format --check` passed for every modified file except `actions.py`, whose pre-existing HEAD content already fails that formatter check and was intentionally not broadly reformatted. `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` passed (90 tests), and `git diff --check` passed.
