# Resumable Background Full-Index Refresh

Status: needs-triage
Priority: low

## Problem Statement

A full metadata refresh can take many minutes for a large photo library. The current background operation does not retain durable progress, so an application exit or interruption requires another full scan.

## Desired Outcome

Keep normal index updates incremental while making a long full refresh resumable after restart. The UI remains usable, reports non-modal progress, and searches use the last committed index snapshot throughout the refresh.

## Proposed Scope

- Process full-refresh metadata work in bounded ExifTool batches.
- Commit each completed batch and a durable SQLite checkpoint together.
- Resume an interrupted refresh after application restart rather than beginning from the first photo.
- Show non-modal progress and resumed state.
- Keep confirmed tag mutations responsive rather than queuing them behind the entire refresh.

## Open Triage Decisions

- Checkpoint identity, retention, and how folder membership changes affect resumption.
- Batch size, prioritization, cancellation, and interaction with index writes.
- Automatic versus user-requested refresh policy and user-facing progress/error wording.
- Search consistency guarantees while batches are committed.

## Constraints

- Keep filesystem, ExifTool, and SQLite work off the Qt UI thread.
- Reuse the existing BackgroundCoordinator seam; MainWindow should receive progress and lifecycle facts, not own queue or checkpoint state.
- Preserve incremental changed-file updates outside a full refresh.

## Out of Scope

- Parallel ExifTool scans for one root.
- Cloud synchronization or cross-root indexes.
