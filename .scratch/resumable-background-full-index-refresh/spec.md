# Resumable Background Full-Index Refresh

Status: completed
Priority: low

## Problem Statement

A full metadata refresh can take many minutes for a large photo library. The current background operation does not retain durable progress, so an application exit or interruption requires another full scan. It also holds the per-root write queue for the entire refresh, delaying confirmed tag-mutation index updates.

## Desired Outcome

Keep normal index updates incremental while making a long full refresh resumable after restart. The UI remains usable, reports non-modal progress, and searches use the last committed index snapshot throughout the refresh.

## Resolved Triage

### Durable, streamed work

- Persist the refresh run, pending directory-walk queue, and unfinished discovered paths in the active root's existing `.tagger/index.sqlite` database. Do not use a JSON sidecar.
- Store no durable row for completed photos beyond their normal index records. The checkpoint's storage is bounded by outstanding directories and the unfinished batch.
- Discovery runs off the UI thread and streams paths into the refresh; it must not first construct one monolithic complete manifest. Start indexing after each discovered 1,000-path batch.
- Commit a chunk's index writes and its checkpoint in the same SQLite transaction. Commit when either 1,000 photos have accumulated or 30 seconds have elapsed, checking the time after each existing 200-photo ExifTool subgroup.
- Once initial discovery is exhausted, run one final background reconciliation traversal. It removes deleted paths and re-reads only files added or changed since their earlier chunk. Do not loop until the filesystem is quiet.

### Resume, restart, and failures

- When a root becomes active within one hour of an interrupted refresh, automatically resume its checkpoint. At or after one hour, discard the incomplete checkpoint and start a new full scan.
- Both the automatic stale-index refresh and `:reindex` use this engine. An explicit `:reindex` always discards an existing checkpoint and begins a fresh scan.
- A second `:reindex` for an active root cancels the current run after its current 200-photo subgroup, discards its checkpoint, and begins a fresh scan.
- Add `:cancel`; it stops a running refresh after its current 200-photo subgroup and discards its checkpoint. Application interruption, unlike cancellation, preserves recovery state.
- Retry a failing 200-photo ExifTool subgroup twice with short backoff. After the third failed attempt, finish the refresh as failed, preserve chunks already committed, discard its unfinished checkpoint, and require a later fresh `:reindex`.

### Queueing, search, and feedback

- A refresh yields after every committed chunk. All queued incremental writes for that root, especially confirmed tag-mutation updates, run before its next chunk; those newer states therefore win over older refresh data.
- Search reads remain available through SQLite and see only the last committed snapshot. An already displayed search result never changes automatically during or after refresh; the user reruns the query to see later data.
- Present persistent, non-modal refresh feedback on a secondary footer line so ordinary status messages remain available. Update it no more than once per second.
- The footer distinguishes queued, discovery (`Discovering images for DB index… M indexed`, with a subtle low-frequency animation of `Discovering`), determinate refresh (`Refreshing… M / total (percent)` after discovery completes), resumed, cancelled, failed, and completed (`Complete: updated, removed`) states.

## Constraints

- Keep filesystem, ExifTool, and SQLite work off the Qt UI thread through the existing `BackgroundCoordinator`; MainWindow receives lifecycle and progress facts and does not own queue or checkpoint state.
- Preserve per-root serialized writes and incremental changed-file updates outside a full refresh.
- Do not add parallel ExifTool scans for one root, cloud synchronization, or cross-root indexes.

## Acceptance Criteria

- [x] The root SQLite database atomically persists and resumes an unfinished directory walk and bounded batch without duplicating durable checkpoint state for every completed photo.
- [x] Refresh discovery and indexing start incrementally; no complete initial filesystem manifest is required before the first metadata batch.
- [x] Every chunk commits index state and checkpoint together after at most 1,000 photos or 30 seconds, with ExifTool calls bounded to 200 paths.
- [x] A root activated within one hour resumes an interrupted refresh automatically; an older checkpoint is discarded and a new scan begins.
- [x] Automatic stale refreshes and manual `:reindex` share the refresh engine. `:reindex` and a second in-flight `:reindex` restart fresh as specified.
- [x] `:cancel` safely stops after a subgroup and does not leave resumable state.
- [x] Incremental root writes run between chunks and supersede older refresh data.
- [x] A subgroup is retried twice, then reports a terminal failure while preserving prior committed chunks and removing unfinished state.
- [x] One final reconciliation accounts for additions, deletions, and changed files observed during the streamed refresh without an unbounded quiet-period loop.
- [x] Search and displayed search-result view consistency match the resolved rules.
- [x] Secondary-footer feedback is throttled, persistent, and covers all agreed lifecycle states without replacing ordinary feedback.

## Testing Requirements

- Add deterministic `PhotoIndex` tests for transaction atomicity, checkpoint cleanup/expiry, streamed discovery, resume, restart, and final reconciliation.
- Add deterministic coordinator tests for chunk yielding, write priority, cancellation, repeated `:reindex`, retry/failure behavior, and stale/departed-root safety.
- Add offscreen MainWindow tests for `:reindex`, `:cancel`, lifecycle feedback, and stable displayed search results.
- Run Ruff and the offscreen unittest suite.
