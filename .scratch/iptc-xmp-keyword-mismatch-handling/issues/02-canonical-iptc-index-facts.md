# 02 — Migrate the Photo Index to Canonical IPTC Facts

Status: completed
Category: enhancement
Priority: high
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: None

## Goal

Make `IPTC:Keywords` the sole keyword fact represented by the SQLite photo index, including data already indexed from merged IPTC/XMP values.

## Module and Interface

`PhotoIndex` owns the projection from a `KeywordState` to index facts, including the pure canonical-keyword normalization it needs. Its existing state-update interface remains the seam for callers: callers submit confirmed `KeywordState` values and do not choose a keyword field or derive tags from `state.merged` for indexing.

## Scope

- Store only normalized, de-duplicated `IPTC:Keywords` values in `tags` and `photo_tags`; never index `XMP-dc:Subject` values.
- Preserve the current IPTC-empty meaning: a photo is IPTC-empty when its canonical IPTC fact is empty, regardless of XMP values.
- Version or otherwise invalidate merged-keyword index data. A root with pre-migration rows is not initialized/current until a background full refresh has reread its photo metadata and rebuilt its keyword facts.
- Reuse the existing resumable, background refresh seam; do not read metadata or rebuild the index on the Qt UI thread.
- Ensure confirmed-state index updates, full refreshes, stale-result repairs, searches, and known-tag loading all use the same canonical-IPTC projection.
- Remove orphaned tag rows if the existing index lifecycle does not already do so.

## Acceptance Criteria

- An image with empty IPTC and non-empty XMP is absent from tag-search and known-tag results, but remains IPTC-empty.
- An image with non-empty IPTC and empty XMP is present in tag-search and known-tag results by its IPTC values.
- Existing merged-keyword database rows cannot remain eligible for search after migration; completing the background rebuild produces IPTC-only results.
- Photo discovery, refresh, and confirmed mutation updates retain the established background-work and per-root ordering guarantees.
- Tests cover IPTC/XMP-divergent states, migration/invalidation of an existing database, and all index update paths above.

## Out of Scope

- Detecting or resolving IPTC/XMP discrepancies in the UI.
- SQLite IPTC-empty crosscheck verification and `:resync`; see `../../iptc-empty-sqlite-crosscheck/issues/01-add-iptc-empty-sqlite-crosscheck-and-resync.md`.

## Validation

- Run the focused indexing and coordinator tests, then the full test suite.
- Confirm an existing on-disk index is rebuilt without blocking the UI.

## Completion

Implemented canonical IPTC-only index projection, legacy merged-index invalidation, and resumable background rebuild scheduling.

Validation:

- `ruff format` and `ruff check` passed for modified Python files.
- `python3 -m unittest tests.test_indexing tests.test_background_coordinator` passed (39 tests).
- The Qt offscreen suite was run. Its one failure, `test_non_missing_search_metadata_error_stays_an_ordinary_error`, also fails unchanged at baseline commit `f3bb586`; it is unrelated to this ticket.
