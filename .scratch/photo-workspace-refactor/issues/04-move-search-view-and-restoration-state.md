# Move database-search visibility and restoration state into PhotoWorkspace

Status: ready-for-agent
Blocked by: 03

## Goal

Move the current database-search application and clearing behavior behind the Photo Workspace seam without implementing the incomplete future reverse-search plan.

## Acceptance criteria

- SQLite access and query parsing remain outside `PhotoWorkspace`.
- The module accepts matching normalized identities and applies them only to currently loaded photos using current behavior.
- Clearing search restores visibility using current behavior.
- The module owns the logical state needed to restore the active view; Qt retains pixel scroll values and viewport anchoring.
- Search-result behavior does not alter folder loading, metadata formats, or normal tagging behavior.
- `INDEXING_PLAN.md` is not implemented or used as a behavior authority in this ticket.
- Pure and Windows adapter tests pass.

## Preparation

- Keep the SQLite query in `MainWindow`; pass only normalized matching paths to the Photo Workspace seam.
- Add intent-level workspace operations for applying search matches and clearing search. They should return snapshots, restrict matches to loaded paths, repair selection, and own the logical view to restore.
- Preserve current interaction ordering: applying a database search first disables the IPTC-empty filter; clearing search restores the currently expected unfiltered visibility. Qt continues to preserve scroll anchoring while rendering snapshots.
- Extend pure tests for loaded-path restriction, empty matches, clearing search, active-selection repair, and stale IPTC work after a search transition. Extend the existing Windows adapter characterization test for search rendering and restoration.

## Out of scope

- Completing indexed reverse search (`:search`, `:back`, and full search-result mode) described in `INDEXING_PLAN.md`.
