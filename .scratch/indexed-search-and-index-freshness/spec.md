# Indexed Search and Index Freshness

Status: completed
Priority: medium

## Problem Statement

TAGGER already maintains a per-root SQLite index and runs index reads in the background, but database-search results are limited to photos currently loaded in the Photo Workspace. The intended temporary reverse-search result mode is therefore incomplete. The index also lacks an explicit freshness policy and user-requested full reindex.

## Desired Outcome

Complete indexed reverse search without disturbing the normal folder-tagging workflow, and make index freshness explicit and user-controllable. These are separate deliverables sharing the same SQLite index, so they are tracked as independent tickets rather than one coupled implementation.

## Historical Baseline

Before implementation:

- `PhotoIndex.search_photos()` supported `tag:`, `date:`, and bare tag queries.
- The background coordinator ran identified index reads off the UI thread and rejected stale completions.
- The Photo Workspace intersected database matches with loaded paths, so it could not show all indexed results.
- Per-root serialized index writes and discovery-path sync already existed.

## Ticket Boundaries

1. **Complete indexed reverse-search result mode** owns the user-visible search-result view, its workspace restoration state, commands, and adapter behavior. It does not alter index scheduling or schema.
2. **Index freshness and manual reindexing** owns stale-index detection, background full reindex scheduling, deletion cleanup, and `:reindex`. It does not change search-result view semantics.

Neither ticket is formally blocked by the other: the existing index lifecycle is sufficient to deliver reverse-search behavior, while maintenance work must preserve whatever query interface exists.

## Shared Constraints

- Folder mode remains the default Photo Workspace view.
- SQLite and filesystem work remain off the Qt UI thread through existing coordinator seams.
- Photo Workspace owns logical views, selection, and restoration; Qt owns scroll position and rendering.
- Stale completions must not alter the current workspace or replace current footer feedback.
- An accepted non-empty search result focuses the files pane so keyboard navigation continues from its first photo.
- Confirmed tag mutations remain the only source of immediate index updates.

## Completion

Ticket 01 implemented indexed reverse-search result mode and restoration. Ticket 02 implemented freshness detection, serialized full refresh, deletion cleanup, and `:reindex`.

## Out of Scope

- SQLite schema redesign.
- Global cross-root search.
- New search syntax beyond the current `tag:`, `date:`, and bare-tag forms.
- A new thread pool or direct SQLite/filesystem work in UI callbacks.
