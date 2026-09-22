# 02 — Repair Missing Search Results Locally Before a Full Reindex

Status: completed
Category: bug
Priority: high
Milestone: M2 — Reliable, scalable index operations
Blocked by: 01

## Problem

Ticket 01 correctly repairs a confirmed missing indexed-search result by refreshing the entire index root. On a 29,000-photo root this leaves the user waiting for a long full metadata scan after selecting one broken result.

## Goal

Relieve a confirmed missing active search result quickly, then reconcile only its immediate parent directory. Do not automatically start a recursive whole-root refresh for this trigger.

## Desired Behavior

A repair retains ticket 01's strict trigger: an explicit missing-file metadata-read failure for the selected, current database-search result plus a cheap path-existence check confirming the path is absent.

1. **Evict the exact missing path.** Queue a serialized root-index operation that removes only that path's photo record. It must also remove now-orphaned tag vocabulary records. Once committed, rerun the original query and atomically apply it only if its root, workspace generation, and query remain current.
2. **Reconcile the immediate parent directory.** After the eviction, discover supported photos directly in the missing path's parent directory, without recursing into child directories. Read their current metadata and update their records. Delete index records only for absent paths directly in that same directory. If the original query remains current when this stage completes, rerun and atomically apply it so independently discovered local matches appear.
3. **Leave whole-root repair explicit.** Do not queue ticket 01's recursive root refresh after either local stage. `:reindex` remains the deliberate whole-library repair path.

For example:

- `C:\Users\<user>\Pictures\Fotos\foo\bar\img.jpg` reconciles direct supported photos in `C:\Users\<user>\Pictures\Fotos\foo\bar`, not descendants.
- `C:\Users\<user>\Pictures\Fotos\img2.jpg` reconciles direct supported photos in `C:\Users\<user>\Pictures\Fotos`, not its subfolders.

A local reconciliation may discover a current file in that directory, but must not claim it identified a filesystem rename.

## Constraints

- Keep every filesystem, ExifTool, and SQLite operation behind the background coordinator and its existing per-root serial write queue.
- The new scoped reconciliation must not reuse `PhotoIndex.sync_paths()` with a directory subset: that method's deletion behavior currently applies to the whole root. Provide a scope-aware index interface whose deletion set is limited to the immediate directory.
- Preserve current query, workspace-generation, stale-completion, selection, preview, and normal-tagging protections.
- Confirmed tag metadata queued while either stage runs must serialize afterward and win over older index state.
- Use the existing persistent secondary footer status for queued, eviction, local-reconciliation, completion, and failure feedback. Do not replace ordinary footer feedback or show the triggering missing-file dialog.

## Acceptance Criteria

- [x] A confirmed missing active database-search result queues an exact-path eviction, not a recursive root refresh.
- [x] The eviction removes only the confirmed absent photo and its orphaned tag vocabulary, then refreshes the still-current original query atomically.
- [x] The follow-up reconciliation discovers and indexes direct supported files in only the missing path's parent directory; it does not recurse into child directories or infer rename identity.
- [x] Local deletion cleanup affects only absent indexed paths directly in that directory; indexed paths elsewhere in the root remain intact.
- [x] The local stage refreshes the still-current original query atomically, allowing independently discovered local matches to appear.
- [x] No automatic whole-root refresh follows this trigger; `:reindex` remains available for that purpose.
- [x] Repeated missing results for the same root coalesce into one staged repair while it is pending or running.
- [x] Selection, preview, and tag writes remain usable; queued confirmed metadata is committed after the staged repair.
- [x] Obsolete, superseded, departed, and failed repairs do not replace the current view or ordinary footer feedback.
- [x] Secondary-footer feedback identifies the local repair stages and reports completion or failure.
- [x] Tests cover exact eviction, orphan-tag cleanup, non-recursive parent scanning, scoped deletion safety, local match discovery, deduplication, queued updates, failures, and obsolete completion.

## Out of Scope

- Filesystem rename identification.
- Automatic recursive full-root repair following this trigger.
- The IPTC-empty filter's future `:resync` behavior.

## Comments

Follow-up to ticket 01 after its full-root repair implementation exposed unacceptable latency on a 29,000-photo index root.

Implemented with serialized exact-path eviction and non-recursive parent-directory reconciliation. Validation: `ruff check`, `ruff format --check`, and `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (131 tests) passed.
