# Active Photo Workspace View Indicator

Status: ready-for-agent
Priority: medium

## Problem Statement

The image-files pane does not persistently explain which Photo Workspace view the user is seeing. `PhotoWorkspaceSnapshot.view_mode` distinguishes normal folder, IPTC-empty, and database-search views, but the current `filterInfoLabel` presents only IPTC counts. Search feedback is transient footer text and is overwritten by unrelated background activity.

## Desired Outcome

Keep a compact, persistent view indicator directly above the image-files pane. It must state the current Photo Workspace scope and filter/search state without relying on the footer.

## View Contract

- The indicator is adjacent to the image-files pane, not solely in the status-bar footer.
- Folder view shows `Folder view · <count> photos`.
- An IPTC-empty scan shows `Filtering IPTC-empty · <processed>/<total>` while the source view remains visible.
- A completed IPTC-empty view shows `IPTC-empty · <visible>/<total>`.
- A pending database query shows `Searching index · <query>` while the prior view remains visible.
- A completed database-search view shows `Search: <query> · <count> results · :back`.
- Returning to folder view through Clear, `:back`, Escape, workspace replacement, or a failed/superseded request clears any stale search/filter wording and restores the folder-view indicator.
- Footer messages remain available for transient progress, completion, and errors, but must not be the sole indication of an active view.

## Architecture

- `PhotoWorkspaceSnapshot.view_mode` and its IPTC filter operation/count fields remain the logical source of current view state.
- `MainWindow` owns presentation-only facts not held by the Photo Workspace: the displayed search query, request-pending state, and the Qt label widget.
- Reuse or rename the existing files-pane `filterInfoLabel`; do not create a parallel logical filter state or move query parsing into `PhotoWorkspace`.
- Update the indicator only for the current workspace generation and current search request. Stale completions must not replace its wording.

## Testing Requirements

- Add offscreen adapter coverage for folder, pending/completed IPTC-empty, pending/completed search, clear/back/Escape restoration, and stale request rejection.
- Assert the visible label text rather than private adapter fields.

## Out of Scope

- New query syntax or date-filter semantics.
- A global status/history system.
- Changing Photo Workspace selection, restoration, or SQLite scheduling behavior.
