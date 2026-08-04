# Search Result Missing-File Resync

Status: completed
Priority: high

## Problem Statement

An indexed search can return a path whose file has since been moved, renamed, or deleted. Searching for `Kalanderlerche` returned four results and then showed `Error: File not found`.

## Desired Outcome

When TAGGER encounters a missing file from the active indexed search result, it starts a **stale-result index repair** for that root. The repair removes missing paths from SQLite and indexes independently discovered files with their current tags, without identifying filesystem renames.

## Terminology

**Stale-result index repair**:
A background scan of the index root triggered after TAGGER cannot read metadata from an image file returned by a current indexed search. It removes records for missing files and indexes independently discovered files with their current metadata; it does not identify filesystem renames. It is not the IPTC-empty filter's future `:resync` command.

## Existing Behavior

The completed index-freshness work provides background full reindexing and deletion cleanup through `:reindex`, but the reported missing search-result path does not currently trigger that repair automatically.

## Resolved Triage

- The missing-file failure is reproduced at a selected active indexed-search result's metadata read. An explicit missing-file error plus a cheap path-existence check is the only repair trigger.
- Repair uses the root of the accepted search request. At most one repair can be pending or running for one root; it waits behind prior root writes and completes even after its search or Photo Workspace is superseded.
- A successful repair reruns and atomically applies the original query only while its root, workspace generation, and query remain current. Obsolete repairs do not alter current UI state or ordinary feedback.
- Repair has persistent non-blocking secondary-footer feedback, leaving ordinary footer messages readable. Selection, preview, and normal tagging remain usable; confirmed metadata updates are serialized after repair and win over older index state.
- A scan can independently discover a new path and its current metadata, but does not identify it as a renamed former path.

## Constraints

- Keep filesystem and SQLite work behind the existing background coordinator.
- Preserve current search request, workspace-generation, and stale-completion protections.
- Do not block selection, preview, or normal tagging while repair work runs.
