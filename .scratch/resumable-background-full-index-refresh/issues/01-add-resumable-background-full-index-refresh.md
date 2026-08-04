# 01 — Add Resumable Background Full-Index Refresh

Status: completed
Category: feature
Priority: low
Milestone: M2 — Reliable, scalable index operations
Blocked by: None

## Goal

Replace the monolithic full-root refresh with a durable, streamed refresh that remains responsive, resumes a recently interrupted root, and preserves the existing index/search consistency guarantees.

## Agent Brief

**Current behavior:** `PhotoIndex.sync_root()` builds a complete recursive path list and performs the refresh as one coordinator operation. The per-root serial write queue cannot run confirmed tag-mutation index updates until that operation returns, and restart loses all progress.

**Required behavior:**

- Keep a per-root refresh checkpoint in `.tagger/index.sqlite`, not a JSON sidecar. Persist the unfinished directory walk and unfinished path batch, but do not duplicate completed photo paths solely for refresh recovery.
- Discover paths in the background as a stream. Begin indexing after a discovered 1,000-path batch; do not require a complete manifest before work starts.
- Commit index updates and the checkpoint atomically after 1,000 photos or 30 seconds, with the time boundary evaluated between ExifTool's existing 200-path subgroups.
- Yield the root write queue after each committed chunk. Run all pending incremental writes, including confirmed tag-mutation state updates, before the following chunk.
- Resume automatically when an interrupted root is activated within one hour. At or after one hour, discard the checkpoint and start a new scan. An explicit `:reindex` always starts fresh; a second in-flight `:reindex` restarts fresh after its current subgroup.
- Add a catalogue-backed `:cancel` command that stops the active refresh at a subgroup boundary and discards recovery state. Do not actively interrupt an in-flight ExifTool subprocess.
- Retry a failed 200-photo subgroup twice with short backoff. On the third failure, report the refresh as failed, retain already committed index changes, discard unfinished recovery state, and leave a later `:reindex` as the fresh recovery route.
- After streamed discovery completes, perform exactly one reconciliation traversal that removes deleted paths and re-reads only files added or changed during the refresh. Do not wait for a permanently quiet tree.
- SQLite searches remain available against committed snapshots. Do not automatically replace an already displayed search-result view during or after the refresh.
- Use a throttled (at most once per second), persistent secondary footer line for queued, discovery, determinate progress, resumed, cancelled, failed, and completion states. Ordinary footer messages remain independent.

## Acceptance Criteria

- [x] Checkpoint writes and photo-index writes are atomic, and recovery state is local to the root's existing SQLite database.
- [x] Refresh begins metadata work while directory discovery continues; it commits bounded batches and can resume a recent interruption without repeating completed batches.
- [x] Completion runs one bounded reconciliation pass for membership and changed-file repair.
- [x] Automatic stale refresh and manual refresh use the same engine; explicit restart, cancellation, expiry, retries, and terminal failure follow the agreed contract.
- [x] Confirmed tag mutations and other incremental writes are committed between refresh chunks and win over older refresh state.
- [x] Searches see only committed data and existing displayed result views remain stable.
- [x] `:cancel` is present in the action catalogue and stops safely after the current subgroup.
- [x] The secondary footer supplies the agreed lifecycle feedback without replacing ordinary status messages.
- [x] Tests cover the durable index layer, deterministic coordinator scheduling/failure cases, and offscreen command/UI behavior.

## Validation

- `ruff check` and `ruff format --check` on modified Python files.
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`.
- `git diff --check`.

## Comments

Triage completed with the maintainer on 2026-08-02. The feature is ready for implementation.

Implemented: durable SQLite checkpoints stream directories and 1,000-path chunks; coordinator continuations yield to incremental writes; final reconciliation, retries, restart/resume, and `:cancel` are covered by index, coordinator, and offscreen UI tests.
