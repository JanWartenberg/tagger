# Search Result Missing-File Resync

Status: needs-triage
Priority: high

## Problem Statement

An indexed search can return a path whose file has since been moved, renamed, or deleted. Searching for `Kalanderlerche` returned four results and then showed `Error: File not found`.

## Desired Outcome

When TAGGER encounters a missing file from the active indexed search result, it starts a **stale-result index repair** for that root. The repair removes the missing path from SQLite. If a renamed replacement is found during the scan, its current tags are indexed.

## Terminology

**Stale-result index repair**:
A background root-index refresh triggered because TAGGER cannot read a path returned by an active indexed search. It removes missing index rows and may discover a renamed replacement during its normal scan. It is not the IPTC-empty filter's future `:resync` command.

## Existing Behavior

The completed index-freshness work provides background full reindexing and deletion cleanup through `:reindex`, but the reported missing search-result path does not currently trigger that repair automatically.

## Required Triage

- Reproduce the missing-file result with a deterministic fixture and identify the exact UI and index-I/O path that produces the error.
- Define the stale-result index-repair scope, deduplication, progress, cancellation, and user feedback.
- Define whether and when the active search result view is refreshed after repair.
- Define renamed-file expectations. A full scan can discover a new path and current tags, but does not establish a filesystem rename identity unless separately specified.

## Constraints

- Keep filesystem and SQLite work behind the existing background coordinator.
- Preserve current search request, workspace-generation, and stale-completion protections.
- Do not block selection, preview, or normal tagging while repair work runs.
